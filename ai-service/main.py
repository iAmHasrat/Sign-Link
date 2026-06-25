import base64
import os
import threading
import time
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class FrameRequest(BaseModel):
    image: str


app = FastAPI(title="Sign Link Landmark Service", version="1.0.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "LANDMARK_CORS_ORIGINS",
        ",".join(
            [
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:5175",
                "http://localhost:5176",
                "https://localhost:5173",
                "https://localhost:5174",
                "https://localhost:5175",
                "https://localhost:5176",
                "https://172.16.166.159:5173",
            ]
        ),
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_init_started = time.perf_counter()
hands = mp.solutions.hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=0,
    min_detection_confidence=0.45,
    min_tracking_confidence=0.55,
)
face_mesh = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=False,
    min_detection_confidence=0.55,
    min_tracking_confidence=0.5,
)
model_init_elapsed_ms = (time.perf_counter() - model_init_started) * 1000
print(f"[MediaPipe] Model initialization time: {model_init_elapsed_ms:.0f} ms")

mediapipe_lock = threading.Lock()
request_count = 0
total_detection_ms = 0.0
last_metrics_log = time.perf_counter()
max_frame_width = int(os.getenv("LANDMARK_MAX_FRAME_WIDTH", "640"))
max_frame_height = int(os.getenv("LANDMARK_MAX_FRAME_HEIGHT", "480"))


def decode_image(data_url: str) -> np.ndarray:
    try:
        payload = data_url.split(",", 1)[1] if "," in data_url else data_url
        image_bytes = base64.b64decode(payload)
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image") from exc

    if frame is None:
        raise HTTPException(status_code=400, detail="Unable to decode image")
    return frame


def resize_for_detection(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    scale = min(max_frame_width / width, max_frame_height / height, 1.0)
    if scale >= 1.0:
        return frame
    return cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)


def landmark_to_dict(landmark: Any, index: int) -> dict[str, float | int]:
    return {
        "index": index,
        "x": float(landmark.x),
        "y": float(landmark.y),
        "z": float(landmark.z),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sign-link-landmarks"}


@app.post("/api/landmarks")
def detect_landmarks(payload: FrameRequest) -> dict[str, Any]:
    global last_metrics_log, request_count, total_detection_ms

    request_started = time.perf_counter()
    frame = resize_for_detection(decode_image(payload.image))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = frame.shape[:2]

    with mediapipe_lock:
        hand_results = hands.process(rgb)
        face_results = face_mesh.process(rgb)

    detected_hands = []
    if hand_results.multi_hand_landmarks:
        handedness_list = hand_results.multi_handedness or []
        for hand_index, hand_landmarks in enumerate(hand_results.multi_hand_landmarks):
            handedness = None
            if hand_index < len(handedness_list):
                handedness = handedness_list[hand_index].classification[0].label
            detected_hands.append(
                {
                    "handedness": handedness,
                    "landmarks": [
                        landmark_to_dict(landmark, index)
                        for index, landmark in enumerate(hand_landmarks.landmark)
                    ],
                }
            )

    faces = []
    if face_results.multi_face_landmarks:
      for face_landmarks in face_results.multi_face_landmarks:
          faces.append(
              {
                  "landmarks": [
                      landmark_to_dict(landmark, index)
                      for index, landmark in enumerate(face_landmarks.landmark)
                  ]
              }
          )

    elapsed_ms = (time.perf_counter() - request_started) * 1000
    request_count += 1
    total_detection_ms += elapsed_ms
    now = time.perf_counter()
    if now - last_metrics_log >= 5:
        seconds = now - last_metrics_log
        print(f"[MediaPipe] Detection FPS: {request_count / seconds:.1f}")
        print(f"[MediaPipe] Average detection time: {total_detection_ms / request_count:.0f} ms")
        print(f"[MediaPipe] Last detection time: {elapsed_ms:.0f} ms")
        request_count = 0
        total_detection_ms = 0.0
        last_metrics_log = now

    return {
        "image": {"width": width, "height": height},
        "hands": detected_hands,
        "faces": faces,
        "status": {
            "handsDetected": len(detected_hands),
            "facesDetected": len(faces),
        },
    }


@app.on_event("shutdown")
def shutdown_models() -> None:
    hands.close()
    face_mesh.close()
