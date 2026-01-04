#!/bin/bash

echo "========================================"
echo "  Voice Clone Studio"
echo "========================================"
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found!"
    echo "Please install Python 3.8+"
    exit 1
fi

# Create venv
if [ ! -d "venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Check dependencies
if ! pip show flask &> /dev/null; then
    echo "[2/4] Installing dependencies..."
    echo "This may take 2-3 minutes..."
    echo
    python3 -m pip install -r requirements.txt
    echo "[OK] Dependencies installed"
fi

# Create directories
mkdir -p voice_clones/output
mkdir -p voice_clones/voices
mkdir -p voice_clones/models

# Create config
if [ ! -f "voice_clones/config.json" ]; then
    echo "[3/4] Creating config file..."
    cp config.example.json voice_clones/config.json
    echo "[OK] Config created"
fi

# Check Whisper model
echo "[4/4] Checking Whisper model..."
python3 check_whisper.py
if [ $? -ne 0 ]; then
    echo
    echo "========================================"
    echo "  Whisper Model Not Found"
    echo "========================================"
    echo
    echo "Whisper model is needed for subtitle timestamps."
    echo
    echo "Model location: voice_clones/models/"
    echo
    echo "=== Download Options ==="
    echo
    echo "1. China Mirror (Recommended):"
    echo "   https://hf-mirror.com/Systran/faster-whisper-small"
    echo
    echo "2. Official HuggingFace:"
    echo "   https://huggingface.co/Systran/faster-whisper-small"
    echo
    echo "=== Manual Download Steps ==="
    echo
    echo "1. Download all files from the link above"
    echo "2. Create folder: voice_clones/models/faster-whisper-small/"
    echo "3. Put all downloaded files in that folder"
    echo "4. Restart this script"
    echo
    echo "=== Or Continue Without Whisper ==="
    echo
    echo "Press Enter to continue without Whisper..."
    echo "(Subtitles will use estimated timestamps)"
    echo
    read -p ""
fi

echo
echo "========================================"
echo "  Starting Voice Clone Studio..."
echo "========================================"
echo
echo "  URL: http://localhost:7860"
echo "  Press Ctrl+C to stop"
echo
echo "========================================"
echo

# Start server
python3 voice_clone_flask.py
