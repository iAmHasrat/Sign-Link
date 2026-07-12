"""
generate_isign_gloss_vocab.py
==============================
One-time script: creates a minimal gloss2ids.pkl for iSign.

Why is this needed?
-------------------
RecognitionNetwork always instantiates GlossTokenizer_S2G, which loads a
gloss-to-id mapping from a pickle file (Tokenizer.py line 173).
It requires:
  - '<s>'   mapped to id=0   (silence / blank for CTC)
  - '<unk>' mapped to id=1
  - '<pad>' mapped to id=2

For gloss-free training (recognition_weight=0):
  - All samples pass gloss='' (empty string)
  - ''.split() → [] → gls_lengths=[0] for every sample
  - CTC loss with target_length=0 evaluates to ~0
  - Since recognition_weight=0, it contributes nothing to total loss
  - The GlossTokenizer is still needed to satisfy the model constructor

Run from workspace root:
    python3 generate_isign_gloss_vocab.py

Output:
    data/isign/gloss2ids.pkl
"""

import os
import pickle

OUTPUT_DIR = "data/isign"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Minimum tokens required by GlossTokenizer_S2G:
#   silence_id == 0  (asserted at Tokenizer.py line 208)
gloss2ids = {
    "<s>":   0,   # silence / CTC blank  ← MUST be index 0
    "<unk>": 1,   # unknown gloss
    "<pad>": 2,   # padding
}

output_path = os.path.join(OUTPUT_DIR, "gloss2ids.pkl")
with open(output_path, "wb") as fh:
    pickle.dump(gloss2ids, fh)

print(f"Wrote gloss vocab ({len(gloss2ids)} tokens) to: {output_path}")
print(f"  {gloss2ids}")
