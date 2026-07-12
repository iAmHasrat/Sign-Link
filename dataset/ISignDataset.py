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
    def _read_pose(path: str) -> torch.Tensor:
        """
        Read a .pose file and return a float32 Tensor of shape (T, 2304).

        Steps:
          1.  Pose.read()  →  data (T,1,576,3) + conf (T,1,576)
          2.  Squeeze person dim  →  (T,576,3) and (T,576)
          3.  Expand conf  →  (T,576,1)
          4.  Concat  →  (T,576,4)
          5.  Flatten  →  (T,2304)
        """
        with open(path, "rb") as fh:
            pose = Pose.read(fh.read())

        # Convert masked arrays / custom arrays to plain numpy
        data = np.array(pose.body.data, dtype=np.float32)   # (T, 1, 576, 3)
        conf = np.array(pose.body.confidence, dtype=np.float32)  # (T, 1, 576)

        # Squeeze the person dimension (always 1 for iSign)
        data = data[:, 0, :, :]   # (T, 576, 3)
        conf = conf[:, 0, :]      # (T, 576)

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
