import base64
import os
import threading
import time
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
load_dotenv()

import cv2
import mediapipe as mp
import numpy as np
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class FrameRequest(BaseModel):
    image: str

class SessionFrameRequest(BaseModel):
    session_id: str
    image: str

class SessionControlRequest(BaseModel):
    session_id: str

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
    max_w, max_h = 640, 480
    scale = min(max_w / width, max_h / height, 1.0)
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



app = FastAPI(title="Sign Link AI & Recognition Service", version="2.0.0")

# Setup CORS origins
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
                "*"
            ]
        ),
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For streaming ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global MediaPipe instances
mediapipe_lock = threading.Lock()

# Existing hands & face mesh for backward compatibility
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

# New holistic model for unified body/hand landmark extraction
holistic = mp.solutions.holistic.Holistic(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Active translation sessions state
active_sessions = {}
sessions_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# RULE-BASED GESTURE CLASSIFIER  (replaces GCN model)
# Detects: HELLO, THANK_YOU, GOOD, BAD, LOVE, STOP, TEN, HOW, PEACE, POINT, ONE–FIVE
# ─────────────────────────────────────────────────────────────────────────────

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]
# MediaPipe hand landmark indices: Each finger [MCP, PIP, DIP, TIP]
FINGER_TIPS   = [4, 8, 12, 16, 20]
FINGER_PIPS   = [3, 6, 10, 14, 18]
FINGER_MCPS   = [2, 5, 9, 13, 17]
WRIST         = 0


def _lm(hand_list: list, idx: int) -> dict:
    """Safely get a landmark dict from a flat list of {x,y,z} dicts."""
    if hand_list and idx < len(hand_list):
        return hand_list[idx]
    return {"x": 0.0, "y": 0.0, "z": 0.0}


def _finger_extended(hand: list, tip_idx: int, pip_idx: int, is_thumb: bool = False) -> bool:
    """Return True if the finger is extended (straight out)."""
    tip = _lm(hand, tip_idx)
    pip = _lm(hand, pip_idx)
    if not tip or not pip:
        return False
    if is_thumb:
        mcp = _lm(hand, FINGER_MCPS[0])
        return abs(tip["x"] - mcp["x"]) > abs(pip["x"] - mcp["x"])
    # tip y < pip y means pointing up (y increases downward in image space)
    return tip["y"] < pip["y"]


def count_extended_fingers(hand: list) -> int:
    """Count how many fingers (including thumb) are extended on a hand."""
    if not hand:
        return 0
    total = 0
    if _finger_extended(hand, 4, 3, is_thumb=True):
        total += 1
    for tip, pip in zip(FINGER_TIPS[1:], FINGER_PIPS[1:]):
        if _finger_extended(hand, tip, pip):
            total += 1
    return total


def _wrist_y(hand: list) -> float:
    return _lm(hand, WRIST)["y"] if hand else 1.0

def _wrist_x(hand: list) -> float:
    return _lm(hand, WRIST)["x"] if hand else 0.5

def _wrist_z(hand: list) -> float:
    return _lm(hand, WRIST)["z"] if hand else 0.0


def _wrist_dist_xy(left_hand: list, right_hand: list) -> float:
    lw_x, lw_y = _wrist_x(left_hand), _wrist_y(left_hand)
    rw_x, rw_y = _wrist_x(right_hand), _wrist_y(right_hand)
    return ((lw_x - rw_x) ** 2 + (lw_y - rw_y) ** 2) ** 0.5


def _open_hand(hand: list) -> bool:
    """4 or more fingers extended (open palm)."""
    return count_extended_fingers(hand) >= 4


def _thumb_up(hand: list) -> bool:
    """Thumb up: thumb extended upward, all other fingers folded."""
    if not hand:
        return False
    thumb_tip = _lm(hand, 4)
    thumb_mcp = _lm(hand, 2)
    thumb_pointing_up = thumb_tip["y"] < thumb_mcp["y"] - 0.04
    others_folded = all(
        not _finger_extended(hand, tip, pip)
        for tip, pip in zip(FINGER_TIPS[1:], FINGER_PIPS[1:])
    )
    return thumb_pointing_up and others_folded


def _thumb_down(hand: list) -> bool:
    """Thumb down: thumb tip below wrist, all other fingers folded."""
    if not hand:
        return False
    thumb_tip = _lm(hand, 4)
    wrist     = _lm(hand, WRIST)
    thumb_pointing_down = thumb_tip["y"] > wrist["y"] + 0.04
    others_folded = all(
        not _finger_extended(hand, tip, pip)
        for tip, pip in zip(FINGER_TIPS[1:], FINGER_PIPS[1:])
    )
    return thumb_pointing_down and others_folded


def _love_sign(hand: list) -> bool:
    """ILY: thumb + index + pinky extended; middle + ring folded."""
    if not hand:
        return False
    thumb  = _finger_extended(hand, 4, 3, is_thumb=True)
    index  = _finger_extended(hand, 8, 6)
    middle = _finger_extended(hand, 12, 10)
    ring   = _finger_extended(hand, 16, 14)
    pinky  = _finger_extended(hand, 20, 18)
    return thumb and index and pinky and not middle and not ring


def _peace_sign(hand: list) -> bool:
    """Peace/Victory: index + middle extended; ring + pinky folded."""
    if not hand:
        return False
    index  = _finger_extended(hand, 8, 6)
    middle = _finger_extended(hand, 12, 10)
    ring   = _finger_extended(hand, 16, 14)
    pinky  = _finger_extended(hand, 20, 18)
    return index and middle and not ring and not pinky


def _point_sign(hand: list) -> bool:
    """Pointing: index finger only extended; middle + ring + pinky folded."""
    if not hand:
        return False
    index  = _finger_extended(hand, 8, 6)
    middle = _finger_extended(hand, 12, 10)
    ring   = _finger_extended(hand, 16, 14)
    pinky  = _finger_extended(hand, 20, 18)
    return index and not middle and not ring and not pinky


# Counting words for left hand fingers 1-5
COUNT_WORDS = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE"]


def classify_gesture_rules(pose: list, left_hand: list, right_hand: list) -> tuple[str, float]:
    """
    Classify the current frame's landmarks into a gesture word.
    Returns (gesture_word, confidence) where confidence is 1.0 for all rules
    (rules are deterministic).  Returns ("", 0.0) if no gesture detected.
    """
    has_left  = bool(left_hand)
    has_right = bool(right_hand)

    # ── NAMASTE / THANK_YOU: both hands present and wrists very close ─────────
    if has_left and has_right:
        lw_x, lw_y = _wrist_x(left_hand),  _wrist_y(left_hand)
        rw_x, rw_y = _wrist_x(right_hand), _wrist_y(right_hand)
        dist = ((lw_x - rw_x) ** 2 + (lw_y - rw_y) ** 2) ** 0.5
        if dist < 0.18:
            return ("THANK_YOU", 1.0)

    # ── HELLO / SALUTE: open flat hand raised above midline ───────────────────
    if has_right and _open_hand(right_hand):
        if _wrist_y(right_hand) < 0.42:
            return ("HELLO", 1.0)
    if has_left and _open_hand(left_hand):
        if _wrist_y(left_hand) < 0.42:
            return ("HELLO", 1.0)

    # ── LOVE (ILY sign) ───────────────────────────────────────────────────────
    if has_right and _love_sign(right_hand):
        return ("LOVE", 1.0)
    if has_left and _love_sign(left_hand):
        return ("LOVE", 1.0)

    # ── PEACE / GOODBYE ───────────────────────────────────────────────────────
    if has_right and _peace_sign(right_hand):
        return ("PEACE", 1.0)
    if has_left and _peace_sign(left_hand):
        return ("PEACE", 1.0)

    # ── GOOD: right thumbs up ─────────────────────────────────────────────────
    if has_right and _thumb_up(right_hand):
        return ("GOOD", 1.0)

    # ── BAD: right thumbs down ────────────────────────────────────────────────
    if has_right and _thumb_down(right_hand):
        return ("BAD", 1.0)

    # ── STOP: open hand facing camera at chest level ──────────────────────────
    if has_right and _open_hand(right_hand) and _wrist_y(right_hand) > 0.42:
        return ("STOP", 1.0)

    # ── COUNTING: total extended fingers (both hands combined) ────────────────
    NUMBER_WORDS = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE",
                    "SIX", "SEVEN", "EIGHT", "NINE", "TEN"]
    total_fingers = count_extended_fingers(right_hand) + count_extended_fingers(left_hand)
    # Exclude all-open-hand case (already caught by HELLO/STOP above)
    if 1 <= total_fingers <= 10:
        # Only emit counting if neither hand is in a special shape
        right_special = (has_right and (_thumb_up(right_hand) or _thumb_down(right_hand)
                                        or _love_sign(right_hand) or _peace_sign(right_hand)))
        left_special  = (has_left  and (_thumb_up(left_hand)  or _thumb_down(left_hand)
                                        or _love_sign(left_hand)  or _peace_sign(left_hand)))
        if not right_special and not left_special:
            return (NUMBER_WORDS[total_fingers], 0.90)

    return ("", 0.0)

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
    max_frame_width = int(os.getenv("LANDMARK_MAX_FRAME_WIDTH", "640"))
    max_frame_height = int(os.getenv("LANDMARK_MAX_FRAME_HEIGHT", "480"))
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
    # Returns the API health status along with recognition service state
    return {
        "status": "ok",
        "service": "sign-link-recognition",
        "model_loaded": "true (rule-based gesture classifier)",
        "classes_count": "11",
        "device": "cpu"
    }

def log_prediction(event_type: str, target_indices: list, pred_idx: int, word: str, conf: float, hands_active: bool, is_in_range: bool):
    try:
        with open("c:/Users/hasra/Desktop/signLink word level/gcn_predictions.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event_type} | active={hands_active}, range={is_in_range} | mask_len={len(target_indices)} | pred={pred_idx} ('{word}'), conf={conf:.3f}\n")
    except Exception as e:
        print(f"Failed to write prediction log: {e}")

# Normalization utility for GCN / Transformer model inputs
def preprocess_landmarks(payload: dict) -> list:

    variant = os.getenv("ASL_MODEL_VARIANT", "asl100").strip()
    
    if variant == "casl":
        pose_raw = payload.get("pose")
        lh_raw = payload.get("left_hand")
        rh_raw = payload.get("right_hand")
        
        # 1. Extract 33 Pose landmarks (3D)
        pose = []
        if pose_raw and len(pose_raw) >= 33:
            # MediaPipe Pose has 33 landmarks
            for lm in pose_raw[:33]:
                pose.append([lm.get("x", 0.0), lm.get("y", 0.0), lm.get("z", 0.0)])
        else:
            pose = [[0.0, 0.0, 0.0] for _ in range(33)]
            
        # 2. Extract 21 Left Hand landmarks (3D)
        left_hand = []
        if lh_raw and len(lh_raw) >= 21:
            for lm in lh_raw[:21]:
                left_hand.append([lm.get("x", 0.0), lm.get("y", 0.0), lm.get("z", 0.0)])
        else:
            left_hand = [[0.0, 0.0, 0.0] for _ in range(21)]
            
        # 3. Extract 21 Right Hand landmarks (3D)
        right_hand = []
        if rh_raw and len(rh_raw) >= 21:
            for lm in rh_raw[:21]:
                right_hand.append([lm.get("x", 0.0), lm.get("y", 0.0), lm.get("z", 0.0)])
        else:
            right_hand = [[0.0, 0.0, 0.0] for _ in range(21)]
            
        coords = pose + left_hand + right_hand  # 75 landmarks
        
        # 4. Center relative to Nose (index 0) on x and y axes
        nose_x = coords[0][0]
        nose_y = coords[0][1]
        
        # Flatten into 225 coordinates: [x0, y0, z0, x1, y1, z1, ...]
        flat_features = []
        for pt in coords:
            # Keep missing joints (all zeros) as exactly 0.0 so the model detects hand absence
            if pt[0] == 0.0 and pt[1] == 0.0 and pt[2] == 0.0:
                flat_features.extend([0.0, 0.0, 0.0])
            else:
                nx = pt[0] - nose_x
                ny = pt[1] - nose_y
                nz = pt[2]
                flat_features.extend([nx, ny, nz])
            
        return flat_features
        
    else:
        pose_raw = payload.get("pose")
        pose_indices = [0, 2, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        
        # 1. Extract 13 Pose joints
        pose_joints = []
        if pose_raw and len(pose_raw) >= 17:
            for idx in pose_indices:
                lm = pose_raw[idx]
                pose_joints.append([lm.get("x", 0.0), lm.get("y", 0.0)])
        else:
            pose_joints = [[0.0, 0.0] for _ in range(len(pose_indices))]
            
        # 2. Extract Left Hand (21)
        lh_raw = payload.get("left_hand")
        if lh_raw and len(lh_raw) >= 21:
            left_hand = [[lm.get("x", 0.0), lm.get("y", 0.0)] for lm in lh_raw]
        else:
            left_hand = [[0.0, 0.0] for _ in range(21)]
            
        # 3. Extract Right Hand (21)
        rh_raw = payload.get("right_hand")
        if rh_raw and len(rh_raw) >= 21:
            right_hand = [[lm.get("x", 0.0), lm.get("y", 0.0)] for lm in rh_raw]
        else:
            right_hand = [[0.0, 0.0] for _ in range(21)]
            
        coords = pose_joints + left_hand + right_hand  # shape (55, 2)
        
        # 4. Alignment Normalization (shoulder center alignment and scale normalization)
        l_shoulder = coords[7]  # index 7 is Left Shoulder (pose index 11)
        r_shoulder = coords[8]  # index 8 is Right Shoulder (pose index 12)
        
        cx = (l_shoulder[0] + r_shoulder[0]) / 2.0
        cy = (l_shoulder[1] + r_shoulder[1]) / 2.0
        
        if cx == 0.0 and cy == 0.0:
            cx = 0.5
            cy = 0.5
            
        dx = l_shoulder[0] - r_shoulder[0]
        dy = l_shoulder[1] - r_shoulder[1]
        scale = (dx*dx + dy*dy) ** 0.5
        
        if scale < 0.01:
            scale = 1.0
            
        normalized = []
        for pt in coords:
            nx = (pt[0] - cx) / scale
            ny = (pt[1] - cy) / scale
            normalized.append([nx, ny])
            
        return normalized

# Call LLM backend service (port 8001) to translate gloss sequence to English
async def translate_glosses(gloss_list: list, final: bool = False) -> str:
    if not gloss_list:
        return ""
    text_query = " ".join(gloss_list).upper()
    llm_url = os.getenv("LLM_BACKEND_URL", "http://localhost:8001/translate")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(llm_url, json={"text": text_query, "final": final}, timeout=5.0)
            if response.status_code == 200:
                return response.json().get("corrected_sentence", "")
    except Exception as e:
        print(f"[AI Recognition] Error calling translation backend: {e}")
    # Simple fallback capitalization
    return " ".join(gloss_list).capitalize() + "."

# Endpoint to detect raw hand and face landmarks (backward compatibility)
@app.post("/api/landmarks")
def detect_landmarks(payload: FrameRequest) -> dict[str, Any]:
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

    return {
        "image": {"width": width, "height": height},
        "hands": detected_hands,
        "faces": faces,
        "status": {
            "handsDetected": len(detected_hands),
            "facesDetected": len(faces),
        },
    }

# Real-time WebSocket Translation Pipeline
@app.websocket("/api/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    print("[AI WebSocket] Client connected to translation stream.")
    
    # State machine for gloss filtering (debounce)
    gloss_list = []
    candidate_word = None
    candidate_count = 0
    last_appended_word = None
    import time
    last_appended_time = time.time()
    
    try:
        while True:
            # Receive text payload (JSON)
            data = await websocket.receive_json()
            
            # Check for reset signal
            if data.get("type") == "reset":
                gloss_list.clear()
                candidate_word = None
                candidate_count = 0
                last_appended_word = None
                last_appended_time = time.time()
                await websocket.send_json({
                    "word": "",
                    "confidence": 0.0,
                    "glosses": [],
                    "sentence": ""
                })
                continue
                
            # Support direct client-side gesture predictions
            if data.get("type") == "word":
                word = data.get("word")
                if word and word != last_appended_word:
                    gloss_list.append(word)
                    last_appended_word = word
                    last_appended_time = time.time()
                    print(f"[AI WebSocket] Received direct gesture word: {word}. Sequence: {gloss_list}")
                    current_sentence = await translate_glosses(gloss_list, final=False)
                    await websocket.send_json({
                        "word": word,
                        "confidence": 1.0,
                        "glosses": gloss_list,
                        "sentence": current_sentence
                    })
                continue
                
            if data.get("type") == "finalize":
                if gloss_list:
                    print(f"[AI WebSocket] Received direct finalize. Sequence: {gloss_list}")
                    final_sentence = await translate_glosses(gloss_list, final=True)
                    await websocket.send_json({
                        "word": "",
                        "confidence": 1.0,
                        "glosses": [],
                        "sentence": final_sentence,
                        "final": True
                    })
                    gloss_list.clear()
                    last_appended_word = None
                    candidate_word = None
                    candidate_count = 0
                continue
                
            landmarks_payload = None
            
            # Case 1: Client sends raw base64 frame for server-side Holistic extraction
            if data.get("type") == "frame":
                try:
                    img_data = data.get("image")
                    frame = decode_image(img_data)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    with mediapipe_lock:
                        results = holistic.process(rgb)
                        
                    pose_list = []
                    if results.pose_landmarks:
                        for lm in results.pose_landmarks.landmark:
                            pose_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
                            
                    lh_list = []
                    if results.left_hand_landmarks:
                        for lm in results.left_hand_landmarks.landmark:
                            lh_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
                            
                    rh_list = []
                    if results.right_hand_landmarks:
                        for lm in results.right_hand_landmarks.landmark:
                            rh_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
                            
                    landmarks_payload = {
                        "pose": pose_list,
                        "left_hand": lh_list,
                        "right_hand": rh_list
                    }
                except Exception as e:
                    print("[AI WebSocket] Local Holistic processing error:", e)
                    continue
            
            # Case 2: Client sends pre-extracted landmarks from the browser
            elif data.get("type") == "landmarks":
                landmarks_payload = data.get("landmarks", {})
                
            # Process and translate
            if landmarks_payload:
                # Check hand presence to filter background noise
                lh_raw = landmarks_payload.get("left_hand")
                rh_raw = landmarks_payload.get("right_hand")
                lh_present = lh_raw is not None and len(lh_raw) > 0 and any(lm.get("x", 0.0) != 0.0 for lm in lh_raw)
                rh_present = rh_raw is not None and len(rh_raw) > 0 and any(lm.get("x", 0.0) != 0.0 for lm in rh_raw)
                hands_active = lh_present or rh_present
                
                # Check distance range (gating) using shoulder scale
                pose_raw = landmarks_payload.get("pose")
                is_in_range = True
                if pose_raw and len(pose_raw) >= 13:
                    l_shoulder = pose_raw[11]
                    r_shoulder = pose_raw[12]
                    ls_x, ls_y = l_shoulder.get("x", 0.0), l_shoulder.get("y", 0.0)
                    rs_x, rs_y = r_shoulder.get("x", 0.0), r_shoulder.get("y", 0.0)
                    if not (ls_x == 0.0 and ls_y == 0.0 and rs_x == 0.0 and rs_y == 0.0):
                        dx = ls_x - rs_x
                        dy = ls_y - rs_y
                        sh_scale = (dx*dx + dy*dy) ** 0.5
                        if sh_scale < 0.08 or sh_scale > 0.45:
                            is_in_range = False
                            
                if not is_in_range and hands_active:
                    hands_active = False
                    if not hasattr(websocket_stream, "debug_counter"):
                        websocket_stream.debug_counter = 0
                    if websocket_stream.debug_counter % 30 == 0:
                        print(f"[AI Gating] Signer out of optimal distance bounds")
                

                # Run rule-based gesture classification on current frame
                word = ""
                prob_val = 0.0

                if landmarks_payload:
                    pose_lm   = landmarks_payload.get("pose", [])
                    lh_lm     = landmarks_payload.get("left_hand", [])
                    rh_lm     = landmarks_payload.get("right_hand", [])
                    word, prob_val = classify_gesture_rules(pose_lm, lh_lm, rh_lm)
                    if word:
                        print(f"[AI WebSocket] Rule classified: {word} ({prob_val:.2f})")

                # Filter output through debounce state machine (3 consecutive matches)
                current_sentence = ""
                if prob_val >= 0.80 and word:
                    if word == candidate_word:
                        candidate_count += 1
                    else:
                        candidate_word = word
                        candidate_count = 1

                    if candidate_count >= 3:
                        if word != last_appended_word and word not in ["", "background"]:
                            gloss_list.append(word)
                            last_appended_word = word
                            last_appended_time = time.time()
                            print(f"[AI WebSocket] Appended gloss: {word}. Sequence: {gloss_list}")
                            current_sentence = await translate_glosses(gloss_list, final=False)
                else:
                    # Reset debounce if confidence too low
                    if prob_val < 0.50:
                        candidate_word = None
                        candidate_count = 0

                # Sentence finalization on 2.5 second pause
                if gloss_list and (time.time() - last_appended_time > 2.5):
                    print(f"[AI WebSocket] Pause detected. Finalizing: {gloss_list}")
                    final_sentence = await translate_glosses(gloss_list, final=True)
                    await websocket.send_json({
                        "word": "",
                        "confidence": 1.0,
                        "glosses": [],
                        "sentence": final_sentence,
                        "final": True
                    })
                    gloss_list.clear()
                    last_appended_word = None
                    candidate_word = None
                    candidate_count = 0
                    continue

                # Send live update to client
                await websocket.send_json({
                    "word": word if prob_val >= 0.80 else "",
                    "confidence": float(prob_val),
                    "glosses": gloss_list,
                    "sentence": current_sentence
                })
                    
    except WebSocketDisconnect:
        print("[AI WebSocket] Client disconnected from translation stream.")
    except Exception as e:
        print("[AI WebSocket] WebSocket error occurred:", e)
    finally:
        try:
            await websocket.close()
        except:
            pass

# Helper to read video frames and extract landmark sequences using OpenCV and MediaPipe
async def extract_video_landmarks(video_path: str):
    cap = cv2.VideoCapture(video_path)
    frames_coords = []
    
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Process every 4th frame (~7.5 fps) to match live webcam streaming rate
        if frame_idx % 4 != 0:
            frame_idx += 1
            continue
            
        frame_idx += 1
        
        # Resize frame for faster processing
        frame = resize_for_detection(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        with mediapipe_lock:
            results = holistic.process(rgb)
            
        pose_list = []
        if results.pose_landmarks:
            for lm in results.pose_landmarks.landmark:
                pose_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
                
        lh_list = []
        if results.left_hand_landmarks:
            for lm in results.left_hand_landmarks.landmark:
                lh_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
                
        rh_list = []
        if results.right_hand_landmarks:
            for lm in results.right_hand_landmarks.landmark:
                rh_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
                
        payload = {
            "pose": pose_list,
            "left_hand": lh_list,
            "right_hand": rh_list
        }
        
        normalized = preprocess_landmarks(payload)
        frames_coords.append(normalized)
        
    cap.release()
    return frames_coords

# Translate accumulated coordinate frames using rule-based gesture classifier + LLM
async def translate_gcn_coordinates_sequence(frames_coords: List) -> str:
    """
    Scan a sequence of frame coordinate dicts (each containing pose, left_hand, right_hand)
    and classify per frame with the rule-based classifier, then translate via LLM.
    """
    gloss_list = []
    candidate_word = None
    candidate_count = 0
    last_appended_word = None

    for payload in frames_coords:
        # frames_coords from extract_video_landmarks stores preprocess_landmarks output
        # which is a flat list; but the upstream caller passes the raw dict payload
        pose_lm = payload.get("pose", []) if isinstance(payload, dict) else []
        lh_lm   = payload.get("left_hand", []) if isinstance(payload, dict) else []
        rh_lm   = payload.get("right_hand", []) if isinstance(payload, dict) else []

        word, prob_val = classify_gesture_rules(pose_lm, lh_lm, rh_lm)

        if prob_val >= 0.80 and word:
            if word == candidate_word:
                candidate_count += 1
            else:
                candidate_word = word
                candidate_count = 1

            if candidate_count >= 3:
                if word != last_appended_word and word not in ["", "background"]:
                    gloss_list.append(word)
                    last_appended_word = word
        else:
            if prob_val < 0.50:
                candidate_word = None
                candidate_count = 0

    if gloss_list:
        print(f"[AI Integration] Extracted video glosses: {gloss_list}")
        final_sentence = await translate_glosses(gloss_list, final=True)
        return final_sentence
    else:
        return "No signs detected in the video."


# 1. Start Session Endpoint
@app.post("/api/translate/session/start")
def start_session() -> dict[str, str]:
    session_id = str(uuid.uuid4())
    with sessions_lock:
        active_sessions[session_id] = {
            "gloss_list": [],
            "candidate_word": None,
            "candidate_count": 0,
            "last_appended_word": None,
            "last_appended_time": time.time()
        }
    print(f"[AI Session] Started session: {session_id}")
    return {"session_id": session_id}

# 2. Process Session Frame Endpoint
@app.post("/api/translate/session/frame")
async def process_session_frame(payload: SessionFrameRequest) -> dict[str, Any]:
    session_id = payload.session_id
    with sessions_lock:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        session = active_sessions[session_id]
        
    frame = resize_for_detection(decode_image(payload.image))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = frame.shape[:2]
    
    with mediapipe_lock:
        results = holistic.process(rgb)
        
    pose_list = []
    if results.pose_landmarks:
        for lm in results.pose_landmarks.landmark:
            pose_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
            
    lh_list = []
    if results.left_hand_landmarks:
        for lm in results.left_hand_landmarks.landmark:
            lh_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
            
    rh_list = []
    if results.right_hand_landmarks:
        for lm in results.right_hand_landmarks.landmark:
            rh_list.append({"x": lm.x, "y": lm.y, "z": lm.z})
            
    landmarks_payload = {
        "pose": pose_list,
        "left_hand": lh_list,
        "right_hand": rh_list
    }
    
    # Hand presence checks
    lh_present = len(lh_list) > 0 and any(lm["x"] != 0.0 for lm in lh_list)
    rh_present = len(rh_list) > 0 and any(lm["x"] != 0.0 for lm in rh_list)
    hands_active = lh_present or rh_present
    
    # Distance gating using shoulder scale
    is_in_range = True
    if len(pose_list) >= 13:
        l_shoulder = pose_list[11]
        r_shoulder = pose_list[12]
        ls_x, ls_y = l_shoulder.get("x", 0.0), l_shoulder.get("y", 0.0)
        rs_x, rs_y = r_shoulder.get("x", 0.0), r_shoulder.get("y", 0.0)
        if not (ls_x == 0.0 and ls_y == 0.0 and rs_x == 0.0 and rs_y == 0.0):
            dx = ls_x - rs_x
            dy = ls_y - rs_y
            sh_scale = (dx*dx + dy*dy) ** 0.5
            if sh_scale < 0.08 or sh_scale > 0.45:
                is_in_range = False
                
    if not is_in_range and hands_active:
        hands_active = False
        print(f"[AI Session Gating] Signer out of optimal distance bounds")
        
    # Rule-based gesture classification
    word, prob_val = classify_gesture_rules(pose_list, lh_list, rh_list)
    if word:
        print(f"[AI Session] Rule classified: {word} ({prob_val:.2f})")

    # Run debouncer logic on session variables (3 consecutive matches required)
    if prob_val >= 0.80 and word:
        if word == session["candidate_word"]:
            session["candidate_count"] += 1
        else:
            session["candidate_word"] = word
            session["candidate_count"] = 1

        if session["candidate_count"] >= 3:
            if word != session["last_appended_word"] and word not in ["", "background"]:
                session["gloss_list"].append(word)
                session["last_appended_word"] = word
                session["last_appended_time"] = time.time()
                print(f"[AI Session] Appended gloss: {word}. Sequence: {session['gloss_list']}")
    else:
        if prob_val < 0.50:
            session["candidate_word"] = None
            session["candidate_count"] = 0
                    
    # Format detected hands and faces for response drawing
    detected_hands = []
    if results.left_hand_landmarks:
        detected_hands.append({
            "handedness": "Left",
            "landmarks": [landmark_to_dict(lm, idx) for idx, lm in enumerate(results.left_hand_landmarks.landmark)]
        })
    if results.right_hand_landmarks:
        detected_hands.append({
            "handedness": "Right",
            "landmarks": [landmark_to_dict(lm, idx) for idx, lm in enumerate(results.right_hand_landmarks.landmark)]
        })
        
    detected_faces = []
    if results.face_landmarks:
        detected_faces.append({
            "landmarks": [landmark_to_dict(lm, idx) for idx, lm in enumerate(results.face_landmarks.landmark)]
        })
        
    return {
        "image": {"width": width, "height": height},
        "hands": detected_hands,
        "faces": detected_faces,
        "status": {
            "handsDetected": len(detected_hands),
            "facesDetected": len(detected_faces),
        },
        # Gesture mapper results — consumed by VideoCall.jsx for live feedback
        "gesture": {
            "word": word,
            "confidence": float(prob_val),
            "glosses": list(session["gloss_list"]),
        }
    }

# 3. Stop Session Endpoint
@app.post("/api/translate/session/stop")
async def stop_session(payload: SessionControlRequest) -> dict[str, str]:
    session_id = payload.session_id
    with sessions_lock:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        session = active_sessions.pop(session_id)
        
    gloss_list = session["gloss_list"]
    print(f"[AI Session] Stopping session {session_id}. Gloss list size: {len(gloss_list)}")
    
    if len(gloss_list) == 0:
        return {"translation": "No gestures detected. Please sign in front of the camera."}
        
    translation = await translate_glosses(gloss_list, final=True)
    return {"translation": translation}

# 4. Video Translation Endpoint
@app.post("/api/translate/video")
async def translate_video_file(file: UploadFile = File(...)) -> dict[str, str]:
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"[Video Translate] Uploaded video: {file.filename}")
        
        # Extract sequence features on threadpool
        frames_coords = await run_in_threadpool(extract_video_landmarks, str(temp_path))
        
        if len(frames_coords) == 0:
            return {"translation": "No coordinates extracted from video."}
            
        translation = await translate_gcn_coordinates_sequence(frames_coords)
        return {"translation": translation}
    finally:
        shutil.rmtree(temp_dir)

@app.on_event("shutdown")
def shutdown_models() -> None:
    hands.close()
    face_mesh.close()
    holistic.close()

