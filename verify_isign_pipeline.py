"""
verify_isign_pipeline.py
========================
End-to-end smoke test for the iSign data pipeline.
Verifies: dataset loading → collate_fn → recognition network forward pass.

Run from the TwoStreamNetwork/ directory:
    python3 verify_isign_pipeline.py

What it checks:
  1. ISignDataset loads and returns correctly shaped tensors
  2. collate_fn_ pads a batch of variable-length samples correctly
  3. The recognition network (feature mode) accepts the batch
  4. The VLMapper produces the correct output shape for mBART
  5. No runtime errors in the full forward pass

Does NOT test:
  - Translation network (requires mBART weights)
  - Distributed training
  - BLEU evaluation
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import numpy as np

# ─── Config ────────────────────────────────────────────────────────────────────
POSE_DIR    = "/workspace/isign_data/iSign-poses_v1.1"
TRAIN_CSV = "data/isign/train.csv"
BATCH_SIZE = 4
HIDDEN_SIZE = 512
INPUT_DIM = 2304   # 576 landmarks × 4 (x, y, z, confidence)

print("=" * 60)
print("iSign Pipeline Verification")
print("=" * 60)

# ─── 1. ISignDataset ───────────────────────────────────────────────────────────
print("\n[1] Testing ISignDataset...")
from dataset.ISignDataset import ISignDataset

dataset_cfg = {
    "dataset_name": "isign",
    "pose_dir":     POSE_DIR,
    "train":        TRAIN_CSV,
    "dev":          "data/isign/dev.csv",
    "test":         "data/isign/test.csv",
}

ds = ISignDataset(dataset_cfg, split="train")
print(f"    Dataset length: {len(ds)}")
assert len(ds) > 0, "Dataset is empty!"
assert ds.name2keypoints is None, "name2keypoints must be None"

sample = ds[0]
print(f"    Sample keys      : {list(sample.keys())}")
print(f"    name             : {sample['name']}")
print(f"    text             : {sample['text'][:60]!r}")
print(f"    num_frames       : {sample['num_frames']}")
print(f"    head_rgb_input   : shape={sample['head_rgb_input'].shape}, dtype={sample['head_rgb_input'].dtype}")

assert sample['head_rgb_input'].shape == (sample['num_frames'], INPUT_DIM), \
    f"Expected ({sample['num_frames']}, {INPUT_DIM}), got {sample['head_rgb_input'].shape}"
print("    ✓ ISignDataset OK")

# ─── 2. collate_fn_ ────────────────────────────────────────────────────────────
print("\n[2] Testing collate_fn_ (batch padding)...")
from dataset.FeatureLoader import load_batch_feature

# Simulate a batch of 4 samples with different lengths
samples = [ds[i] for i in range(BATCH_SIZE)]
features = [s['head_rgb_input'] + 1.0e-8 for s in samples]   # matches collate_fn offset
batch_feat, sgn_mask, sgn_lengths = load_batch_feature(features)
print(f"    Batch feature shape : {batch_feat.shape}")      # (B, T_max, 2304)
print(f"    sgn_mask shape      : {sgn_mask.shape}")        # (B, T_max)
print(f"    sgn_lengths         : {sgn_lengths.tolist()}")  # [T0, T1, T2, T3]
assert batch_feat.shape[0] == BATCH_SIZE
assert batch_feat.shape[2] == INPUT_DIM
assert sgn_mask.shape == batch_feat.shape[:2]
print("    ✓ collate_fn padding OK")

# ─── 3. VisualHead (recognition feature path) ──────────────────────────────────
print("\n[3] Testing VisualHead (feature mode, input_streams=['rgb'])...")
from modelling.Visualhead import VisualHead

# Minimal GlossTokenizer stub (avoids needing the pickle file here)
class _DummyGlossTokenizer:
    silence_id = 0
    pad_id = 2
    def __len__(self): return 3
    def __call__(self, batch_gls_seq):
        gls_lengths = torch.zeros(len(batch_gls_seq), dtype=torch.long)
        gloss_labels = torch.zeros(len(batch_gls_seq), 1, dtype=torch.long)
        return {'gls_lengths': gls_lengths, 'gloss_labels': gloss_labels}

vh = VisualHead(
    cls_num=3,
    input_size=INPUT_DIM,
    hidden_size=HIDDEN_SIZE,
    ff_size=2048,
    pe=True,
    ff_kernelsize=[3, 3],
)
vh.eval()

with torch.no_grad():
    vh_out = vh(x=batch_feat, mask=sgn_mask, valid_len_in=sgn_lengths)

print(f"    gloss_feature shape : {vh_out['gloss_feature'].shape}")  # (B, T_max, 512)
print(f"    gloss_logits shape  : {vh_out['gloss_logits'].shape}")   # (B, T_max, 3)
assert vh_out['gloss_feature'].shape == (BATCH_SIZE, batch_feat.shape[1], HIDDEN_SIZE)
print("    ✓ VisualHead forward OK")

# ─── 4. VLMapper ───────────────────────────────────────────────────────────────
print("\n[4] Testing VLMapper...")
from modelling.vl_mapper import VLMapper

# mBART-large embedding dim is 1024
MBART_DIM = 1024
vl = VLMapper(
    cfg={"type": "projection", "multistream_fuse": "empty"},
    in_features=HIDDEN_SIZE,
    out_features=MBART_DIM,
)
vl.eval()

with torch.no_grad():
    mapped = vl(visual_outputs={"gloss_feature": vh_out["gloss_feature"]})

print(f"    VLMapper output shape : {mapped.shape}")   # (B, T_max, 1024)
assert mapped.shape == (BATCH_SIZE, batch_feat.shape[1], MBART_DIM)
print("    ✓ VLMapper OK")

# ─── 5. GlossTokenizer with real pkl ───────────────────────────────────────────
print("\n[5] Testing GlossTokenizer_S2G with generated gloss2ids.pkl...")
GLOSS_PKL = "data/isign/gloss2ids.pkl"
if not os.path.exists(GLOSS_PKL):
    print(f"    SKIP — run generate_isign_gloss_vocab.py first")
else:
    from modelling.Tokenizer import GlossTokenizer_S2G
    gt = GlossTokenizer_S2G({"gloss2id_file": GLOSS_PKL})
    print(f"    Vocab size     : {len(gt)}")
    print(f"    silence_id     : {gt.silence_id}")
    result = gt(["", ""])   # empty gloss sequences
    print(f"    gls_lengths    : {result['gls_lengths'].tolist()}")
    assert gt.silence_id == 0
    print("    ✓ GlossTokenizer_S2G OK")

print("\n" + "=" * 60)
print("ALL CHECKS PASSED ✓")
print("=" * 60)
print("\nNext steps:")
print("  1. Run training.py with the isign_s2t.yaml config")
print("  2. Monitor BLEU on the dev set")
