"""
check_isign_pretrained.py
==========================
Checks what pretrained models are available and whether they support English.
Run this BEFORE editing isign_s2t.yaml so you know the correct paths.

    python3 check_isign_pretrained.py
"""

import os, glob

print("=" * 60)
print("Pretrained model directories found:")
print("=" * 60)

for candidate in sorted(glob.glob("pretrained_models/*")):
    print(f"\n  {candidate}/")
    for f in sorted(os.listdir(candidate))[:15]:
        print(f"    {f}")

print("\n" + "=" * 60)
print("Checking for mBART / tokenizer config files:")
print("=" * 60)
for f in sorted(glob.glob("pretrained_models/**/*", recursive=True)):
    bn = os.path.basename(f)
    if any(kw in bn for kw in ["tokenizer", "config", "sentencepiece", "vocab", "lang"]):
        print(f"  {f}")

print("\n" + "=" * 60)
print("Checking tokenizer language support:")
print("=" * 60)
try:
    from transformers import MBartTokenizer
    for model_dir in sorted(glob.glob("pretrained_models/*")):
        try:
            tok = MBartTokenizer.from_pretrained(model_dir)
            langs = getattr(tok, 'additional_special_tokens', [])
            has_en = 'en_XX' in str(langs)
            print(f"  {model_dir}: tgt_lang support → en_XX={'YES' if has_en else 'NO'}")
            print(f"    special tokens (first 10): {langs[:10]}")
        except Exception as e:
            print(f"  {model_dir}: could not load → {e}")
except ImportError:
    print("  transformers not available")
