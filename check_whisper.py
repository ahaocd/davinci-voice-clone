#!/usr/bin/env python3
"""
Check if Whisper model exists locally.
Exit code 0 = model found, 1 = not found
"""

import os
import sys

MODEL_DIR = os.path.join("voice_clones", "models", "faster-whisper-small")

# Required model files
REQUIRED_FILES = [
    "model.bin",
    "config.json",
    "vocabulary.json",
    "tokenizer.json"
]

def check_model():
    """Check if Whisper model exists and is complete."""
    if not os.path.isdir(MODEL_DIR):
        return False
    
    # Check for required files
    for filename in REQUIRED_FILES:
        filepath = os.path.join(MODEL_DIR, filename)
        if not os.path.isfile(filepath):
            return False
    
    return True

if __name__ == "__main__":
    if check_model():
        print("[OK] Whisper model found")
        sys.exit(0)
    else:
        sys.exit(1)
