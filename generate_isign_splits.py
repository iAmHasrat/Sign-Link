"""
generate_isign_splits.py
========================
One-time script: splits the iSign CSV into train / dev / test CSVs.

Strategy
--------
- Filter rows with null 'text' first (391 rows).
- Shuffle with fixed seed=42 for reproducibility.
- Split ratio: 80% train / 10% dev / 10% test.
- Write three CSV files that ISignDataset will read directly.

Run from the workspace root:
    python3 generate_isign_splits.py

Outputs (written to data/isign/):
    data/isign/train.csv
    data/isign/dev.csv
    data/isign/test.csv
"""

import os
import pandas as pd
from sklearn.model_selection import train_test_split

# Absolute path — source CSV lives at /workspace, not inside TwoStreamNetwork/
CSV_PATH   = "/workspace/iSign/iSign_v1.1.csv"
OUTPUT_DIR = "data/isign"   # relative to TwoStreamNetwork/ — correct
SEED       = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load & clean ───────────────────────────────────────────────────────────────
df = pd.read_csv(CSV_PATH, dtype=str)
print(f"Total rows loaded   : {len(df)}")

df = df.dropna(subset=["text"]).reset_index(drop=True)
print(f"After dropping nulls: {len(df)}")

# ── Split: 80 / 10 / 10 ────────────────────────────────────────────────────────
# First: carve off the test set (10% of total)
train_val, test = train_test_split(df, test_size=0.10, random_state=SEED, shuffle=True)
# Then: from the remaining 90%, carve off dev (~11.1% of 90% ≈ 10% of total)
train, dev = train_test_split(train_val, test_size=0.1111, random_state=SEED, shuffle=True)

print(f"Train samples : {len(train)}")
print(f"Dev   samples : {len(dev)}")
print(f"Test  samples : {len(test)}")
assert len(train) + len(dev) + len(test) == len(df), "Split sizes don't add up!"

# ── Write ──────────────────────────────────────────────────────────────────────
train.to_csv(os.path.join(OUTPUT_DIR, "train.csv"), index=False)
dev.to_csv(  os.path.join(OUTPUT_DIR, "dev.csv"),   index=False)
test.to_csv( os.path.join(OUTPUT_DIR, "test.csv"),  index=False)

print(f"\nSplit CSVs written to: {OUTPUT_DIR}/")
print("  train.csv, dev.csv, test.csv")
