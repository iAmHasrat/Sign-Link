"""
ISignDataset — adapts the iSign-poses_v1.1 dataset for TwoStreamNetwork.

Pipeline per sample:
  .pose file
    ↓  Pose.read()
    ↓  data:  (T, 1, 576, 3)   float32   (x, y, z coordinates)
    ↓  conf:  (T, 1, 576)      float32   (landmark confidence)
    ↓  squeeze person dim
    ↓  data:  (T, 576, 3)
    ↓  conf:  (T, 576, 1)   ← expand last dim for concat
    ↓  concat on axis=-1  →  (T, 576, 4)
    ↓  flatten landmarks  →  (T, 2304)   float32 Tensor

Returned dict keys:
    "name"          — uid string (used for logging / WER / BLEU lookup)
    "text"          — English sentence (consumed by TextTokenizer in collate_fn)
    "num_frames"    — integer T (used by Dataloader for length bookkeeping)
    "head_rgb_input" — Tensor(T, 2304)
        Why this key and not "sgn_features"?
        Dataloader.collate_fn_ (line 40-44) iterates over
        ['sgn_features', 'head_rgb_input', 'head_keypoint_input']
        and calls load_batch_feature on whichever key is present.
        RecognitionNetwork.forward() (feature mode, input_streams=['rgb'],
        line 584) then receives it as the `head_rgb_input` kwarg.
        Using 'head_rgb_input' keeps our data flowing through the existing
        single-stream feature path with zero changes to recognition.py.

Compatibility contract (required by Dataloader.py line 82):
    dataset.name2keypoints  must exist and be None
    (Dataloader passes it to collate_fn as name2keypoint=dataset.name2keypoints)
"""

import os
import numpy as np
import pandas as pd
import torch
from pose_format import Pose
import logging as _logging


class ISignDataset(torch.utils.data.Dataset):
    """
    Dataset for the iSign pose-based sign language translation corpus.

    Args:
        dataset_cfg (dict): The 'data' section of the YAML config.
            Required keys:
                dataset_name  : 'isign'
                train / dev / test : path to split-specific CSV files
                pose_dir      : path to the directory containing .pose files
        split (str): One of 'train', 'dev', 'test'.
    """

    # mBART max_position_embeddings=1024, offset=2, suffix=2 (</s> + en_ISL)
    # So max input frames = 1024 - 2 - 2 = 1020
    MAX_SEQ_LEN = 1020

    # Expose None so Dataloader.py can pass it as name2keypoint=None
    # without special-casing ISignDataset anywhere.
    name2keypoints = None

    def __init__(self, dataset_cfg: dict, split: str) -> None:
        super().__init__()
        self.split = split
        self.dataset_cfg = dataset_cfg
        self.pose_dir = dataset_cfg["pose_dir"]
        try:
            from utils.misc import get_logger
            self.logger = get_logger()
        except Exception:
            self.logger = _logging.getLogger(__name__)
        self._load_annotations()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_annotations(self) -> None:
        """
        Read the split-specific CSV, drop rows with missing text,
        and store the resulting DataFrame as self.annotations.

        The CSV must have at least two columns: 'uid' and 'text'.
        'uid' maps 1-to-1 to a .pose filename:  <uid>.pose
        """
        csv_path = self.dataset_cfg[self.split]
        df = pd.read_csv(csv_path, dtype=str)  # read as str to avoid uid mangling

        n_before = len(df)
        # Drop rows where the English translation is missing
        df = df.dropna(subset=["text"]).reset_index(drop=True)
        n_dropped = n_before - len(df)

        if n_dropped > 0:
            self.logger.info(
                f"ISignDataset [{self.split}]: dropped {n_dropped} rows "
                f"with null text (kept {len(df)})"
            )
        else:
            self.logger.info(
                f"ISignDataset [{self.split}]: {len(df)} samples loaded"
            )

        self.annotations = df[["uid", "text"]]

    @staticmethod
    def _normalize_landmarks(data: np.ndarray) -> np.ndarray:
        """
        Normalize MediaPipe Holistic landmark coordinates:
          1. Hips midpoint as origin for body and face.
          2. Left/right wrist as origin for left/right hand.
          3. Scale normalization by shoulder-to-shoulder width.
        """
        T, N, C = data.shape
        normalized = np.copy(data)
        
        # 1. Hips midpoint centering (origin for pose and face)
        # Left hip: 23, Right hip: 24
        mid_hips = (data[:, 23, :C] + data[:, 24, :C]) / 2.0  # (T, 3)
        pose_face_end = min(501, N)
        normalized[:, :pose_face_end, :C] -= mid_hips[:, np.newaxis, :]
        
        # 2. Wrist-relative hand coordinates
        # Left hand wrist: index 501. Left hand: 501 to 521
        if N > 501:
            left_hand_end = min(522, N)
            left_wrist = data[:, 501, :C]  # (T, 3)
            normalized[:, 501:left_hand_end, :C] -= left_wrist[:, np.newaxis, :]
            
        # Right hand wrist: index 522. Right hand: 522 to 542
        if N > 522:
            right_hand_end = min(543, N)
            right_wrist = data[:, 522, :C]  # (T, 3)
            normalized[:, 522:right_hand_end, :C] -= right_wrist[:, np.newaxis, :]
            
        # 3. Scale normalization by shoulder-to-shoulder width
        # Left shoulder: 11, Right shoulder: 12
        shoulder_dist = np.linalg.norm(data[:, 11, :C] - data[:, 12, :C], axis=-1, keepdims=True)  # (T, 1)
        shoulder_dist = np.where(shoulder_dist == 0.0, 1.0, shoulder_dist)
        
        # Apply scaling to all coordinates
        normalized[:, :, :C] /= shoulder_dist[:, np.newaxis, :]
        
        return normalized

    def _read_pose(self, path: str) -> torch.Tensor:
        """
        Read a .pose file, apply normalization and split-dependent data augmentations,
        and return a float32 Tensor of shape (T, 2304).
        """
        with open(path, "rb") as fh:
            pose = Pose.read(fh.read())

        # Convert masked arrays / custom arrays to plain numpy
        data = np.array(pose.body.data, dtype=np.float32)   # (T, 1, 576, 3)
        conf = np.array(pose.body.confidence, dtype=np.float32)  # (T, 1, 576)

        # Squeeze the person dimension (always 1 for iSign)
        data = data[:, 0, :, :]   # (T, 576, 3)
        conf = conf[:, 0, :]      # (T, 576)

        # Apply normalization
        data = self._normalize_landmarks(data)

        # Apply split-dependent train-time augmentations
        if self.split == "train":
            T, N, C = data.shape
            
            # A. Temporal Stretching/Compression (Frame Resampling)
            if np.random.rand() < 0.5:
                scale = np.random.uniform(0.8, 1.2)
                new_T = int(round(T * scale))
                new_T = max(8, min(new_T, self.MAX_SEQ_LEN))
                indices = np.linspace(0, T - 1, new_T).astype(np.int32)
                data = data[indices]
                conf = conf[indices]
                T = new_T

            # B. Landmark Dropout (Masking left/right hands randomly)
            if np.random.rand() < 0.1:  # 10% chance to drop left hand
                if N > 501:
                    left_hand_end = min(522, N)
                    data[:, 501:left_hand_end, :] = 0.0
                    conf[:, 501:left_hand_end] = 0.0
            if np.random.rand() < 0.1:  # 10% chance to drop right hand
                if N > 522:
                    right_hand_end = min(543, N)
                    data[:, 522:right_hand_end, :] = 0.0
                    conf[:, 522:right_hand_end] = 0.0

            # C. Random Rotation (around Z axis)
            if np.random.rand() < 0.5:
                angle = np.random.uniform(-0.1, 0.1)  # in radians
                cos_a, sin_a = np.cos(angle), np.sin(angle)
                rot_matrix = np.array([[cos_a, -sin_a, 0], [sin_a, cos_a, 0], [0, 0, 1]], dtype=np.float32)
                data = np.dot(data, rot_matrix)

            # D. Random Scaling
            if np.random.rand() < 0.5:
                scale_factor = np.random.uniform(0.95, 1.05)
                data *= scale_factor

            # E. Gaussian Noise
            if np.random.rand() < 0.5:
                noise = np.random.normal(0.0, 0.01, size=data.shape).astype(np.float32)
                data += noise

        # Append confidence as a 4th channel per landmark
        conf = conf[:, :, np.newaxis]               # (T, 576, 1)
        combined = np.concatenate([data, conf], axis=-1)  # (T, 576, 4)

        # Flatten landmark × channel into a single feature vector
        T = combined.shape[0]
        flat = combined.reshape(T, -1)              # (T, 2304)

        return torch.from_numpy(flat)

    # ------------------------------------------------------------------
    # torch.utils.data.Dataset interface
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.annotations)

    def __getitem__(self, idx: int) -> dict:
        """
        Returns a single sample dict.

        Key "head_rgb_input" (not "sgn_features") is intentional — see module
        docstring for the full explanation of why this key is used.
        """
        row = self.annotations.iloc[idx]
        uid: str = row["uid"]
        text: str = row["text"]

        pose_path = os.path.join(self.pose_dir, uid + ".pose")

        if not os.path.exists(pose_path):
            raise FileNotFoundError(
                f"Pose file not found for uid='{uid}': {pose_path}"
            )

        sgn_features = self._read_pose(pose_path)  # (T, 2304)

        # Truncate to avoid exceeding mBART positional embedding limit
        if sgn_features.shape[0] > self.MAX_SEQ_LEN:
            sgn_features = sgn_features[:self.MAX_SEQ_LEN]

        return {
            "name": uid,
            "text": text,
            "num_frames": sgn_features.shape[0],
            # This key feeds the single-stream feature path in
            # RecognitionNetwork.forward() when input_streams=['rgb'].
            "head_rgb_input": sgn_features,
        }
