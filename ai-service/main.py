import base64
import os
import threading
import time
from typing import Any

from dotenv import load_dotenv
load_dotenv()

import cv2
import mediapipe as mp
import numpy as np
import torch
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from huggingface_hub import hf_hub_download

# Import GCN model and configs from local files
from configs import Config
from tgcn_model import GCN_muti_att

class FrameRequest(BaseModel):
    image: str

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

# Recognition Model global variables
model = None
wlasl_classes = []
device = "cuda" if torch.cuda.is_available() else "cpu"

@app.on_event("startup")
def load_recognition_model():
    global model, wlasl_classes
    variant = os.getenv("ASL_MODEL_VARIANT", "asl100").strip()
    
    if variant == "casl":
        print("[AI Recognition] Loading CASL-TransSLR model (60 classes)...")
        repo_id = "luciayen/CASL-TransSLR"
        try:
            import importlib.util
            model_bin = hf_hub_download(repo_id=repo_id, filename="pytorch_model.bin", token=False)
            model_script = hf_hub_download(repo_id=repo_id, filename="model.py", token=False)
            
            spec = importlib.util.spec_from_file_location("model_arch", model_script)
            model_arch = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(model_arch)
            
            model = model_arch.SignVLM().to(device)
            model.load_state_dict(torch.load(model_bin, map_location=device))
            model.eval()
            
            # CASL 60 words
            wlasl_classes = [
                "To call", "Blue", "How", "Hard", "Family", "(Name) Sign", "Fight", "Gift", 
                "Chair", "Sleep", "School", "Cold", "War", "Wrong", "Brown", "Beggar", 
                "THANKS", "Don't know", "Black", "Forget", "Papa", "Police", "Radio", "Seasons", 
                "Wash yourself", "Seven", "Sign awkwardly", "Deaf", "Taxi", "Tiger", "Car accident", "Good", 
                "White", "comical", "Concentrate", "Wooden pencil", "Sorry", "Difficult", "Water", "Hearing", 
                "Soccer", "Goalkeeper", "Juice", "Lion", "Mom", "Motorbike", "Not", "Santa Claus", 
                "Whatever", "For what", "Issue", "Region", "Red", "Mock", "Practice", "Stubborn", 
                "Green", "Quickly", "Car", "Flight"
            ]
            print(f"[AI Recognition] CASL-TransSLR model successfully loaded. Classes: {len(wlasl_classes)}")
        except Exception as e:
            print(f"[AI Recognition] Failed to load CASL-TransSLR model: {e}")
    else:
        repo_id = "sharonn18/tgcn-wlasl"
        # Map variant names to exact class counts
        variant_classes = {
            "asl100": 100,
            "asl300": 300,
            "asl1000": 1000,
            "asl2000": 2000
        }
        num_classes = variant_classes.get(variant, 100)
        
        print(f"[AI Recognition] Loading model variant: {variant} ({num_classes} classes)...")
        print(f"[AI Recognition] Downloading pre-trained {variant} weights from HuggingFace...")
        try:
            # Download config and weights dynamically for this variant
            config_path = hf_hub_download(repo_id=repo_id, filename=f"checkpoints/{variant}/config.ini", token=False)
            checkpoint_path = hf_hub_download(repo_id=repo_id, filename=f"checkpoints/{variant}/pytorch_model.bin", token=False)
            
            # Initialize model with correct parameters
            config = Config(config_path)
            model = GCN_muti_att(
                input_feature=config.num_samples * 2,  # 50 * 2 = 100
                hidden_feature=config.hidden_size,
                num_class=num_classes,
                p_dropout=config.drop_p,
                num_stage=config.num_stages
            )
            
            # Load weights
            checkpoint = torch.load(checkpoint_path, map_location=device)
            state_dict = checkpoint.get('state_dict', checkpoint)
            model.load_state_dict(state_dict, strict=False)
            model.to(device)
            model.eval()
            print(f"[AI Recognition] {variant} model successfully loaded on device: {device}")
        except Exception as e:
            print(f"[AI Recognition] Failed to load model weights: {e}")

        # Load classes mapping
        class_file = "wlasl_class_list.txt"
        try:
            with open(class_file, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        wlasl_classes.append(parts[1])
            # Slice classes vocabulary to match model's expected output count
            wlasl_classes = wlasl_classes[:num_classes]
            print(f"[AI Recognition] Loaded {len(wlasl_classes)} classes for {variant} successfully.")
        except Exception as e:
            print(f"[AI Recognition] Failed to load class mapping file: {e}")

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
    model_loaded = model is not None
    classes_loaded = len(wlasl_classes) > 0
    return {
        "status": "ok",
        "service": "sign-link-recognition",
        "model_loaded": str(model_loaded),
        "classes_count": str(len(wlasl_classes)),
        "device": device
    }

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
    
    # Initialize sliding sequence buffer of 50 frames with zero padding
    variant = os.getenv("ASL_MODEL_VARIANT", "asl100").strip()
    
    # Initialize sliding sequence buffer of frames with zero padding
    frame_buffer = []
    if variant == "casl":
        for _ in range(64):
            frame_buffer.append([0.0 for _ in range(225)])
    else:
        for _ in range(50):
            frame_buffer.append([[0.0, 0.0] for _ in range(55)])
        
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
                if variant == "casl":
                    frame_buffer = [[0.0 for _ in range(225)] for _ in range(64)]
                else:
                    frame_buffer = [[[0.0, 0.0] for _ in range(55)] for _ in range(50)]
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
                normalized_coords = preprocess_landmarks(landmarks_payload)
                
                # Check hand presence to filter background noise
                lh_raw = landmarks_payload.get("left_hand")
                rh_raw = landmarks_payload.get("right_hand")
                lh_present = lh_raw is not None and len(lh_raw) > 0 and any(lm.get("x", 0.0) != 0.0 for lm in lh_raw)
                rh_present = rh_raw is not None and len(rh_raw) > 0 and any(lm.get("x", 0.0) != 0.0 for lm in rh_raw)
                hands_active = lh_present or rh_present
                
                # Diagnostic logging once per second (every 30 frames)
                if not hasattr(websocket_stream, "debug_counter"):
                    websocket_stream.debug_counter = 0
                websocket_stream.debug_counter += 1
                if websocket_stream.debug_counter % 30 == 0:
                    print(f"[AI Debug] hands_active={hands_active}, lh_present={lh_present}, rh_present={rh_present}, buffer_len={len(frame_buffer)}")
                
                # Push to sliding history buffer
                frame_buffer.append(normalized_coords)
                max_frames = 64 if variant == "casl" else 50
                if len(frame_buffer) > max_frames:
                    frame_buffer.pop(0)
                    
                # Run inference if model is ready and hands are active
                word = ""
                prob_val = 0.0
                
                if model is not None and len(wlasl_classes) > 0:
                    if hands_active:
                        if variant == "casl":
                            # Convert to PyTorch tensor directly: shape (1, 64, 225)
                            x_tensor = torch.tensor(frame_buffer, dtype=torch.float32).unsqueeze(0).to(device)
                        else:
                            # GCN Shape conversions: (50, 55, 2) -> (55, 50, 2) -> (55, 100)
                            arr = np.array(frame_buffer)
                            flat = arr.transpose(1, 0, 2).reshape(55, 100)
                            x_tensor = torch.tensor(flat, dtype=torch.float32).unsqueeze(0).to(device)
                        
                        with torch.no_grad():
                            output = model(x_tensor)
                            probs = torch.softmax(output, dim=1)
                            conf, pred_idx = torch.max(probs, dim=1)
                            
                        prob_val = conf.item()
                        word = wlasl_classes[pred_idx.item()]
                    else:
                        # Clear buffer when hands are inactive to discard stale movements
                        if variant == "casl":
                            frame_buffer = [[0.0 for _ in range(225)] for _ in range(64)]
                        else:
                            frame_buffer = [[[0.0, 0.0] for _ in range(55)] for _ in range(50)]
                    
                    # Debug print prediction with high confidence
                    # if prob_val > 0.35:
                    #     print(f"Pred: {word} ({prob_val:.2f})")
                        
                    # Filter output through sequence state machine (debounce filter)
                    # Requires a prediction threshold of 0.40 and 3 consecutive matches
                    current_sentence = ""
                    if prob_val >= 0.40:
                        if word == candidate_word:
                            candidate_count += 1
                        else:
                            candidate_word = word
                            candidate_count = 1
                            
                        if candidate_count >= 3:
                            if word != last_appended_word and word not in ["background", "no_sign", "wait"]:
                                gloss_list.append(word)
                                last_appended_word = word
                                last_appended_time = time.time()
                                print(f"[AI WebSocket] Appended gloss: {word}. Sequence: {gloss_list}")
                                # Trigger translation call
                                current_sentence = await translate_glosses(gloss_list, final=False)
                    
                    # Check for pause / sentence finalization (2.5 seconds timeout)
                    if gloss_list and (time.time() - last_appended_time > 2.5):
                        print(f"[AI WebSocket] Pause detected. Finalizing sequence: {gloss_list}")
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
                    
                    # Send response back to the client
                    await websocket.send_json({
                        "word": word if prob_val >= 0.35 else "",
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

@app.on_event("shutdown")
def shutdown_models() -> None:
    hands.close()
    face_mesh.close()
    holistic.close()
