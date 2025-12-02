#!/bin/bash

echo "========================================"
echo "Purchase Tracker Backend - Quick Start"
echo "========================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

echo "[1/5] Checking Python version..."
python3 --version

echo
echo "[2/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created successfully"
else
    echo "Virtual environment already exists"
fi

echo
echo "[3/5] Activating virtual environment..."
source venv/bin/activate

echo
echo "[4/5] Installing dependencies..."
pip install --quiet --upgrade pip
pip install -r requirements.txt

echo
echo "[5/5] Checking setup..."
python test_setup.py

echo
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo
echo "Next steps:"
echo "1. Make sure you have credentials.json in the project root"
echo "2. Create and configure .env file (see ENV_EXAMPLE.txt)"
echo "3. Run: python run.py"
echo
echo "For detailed setup instructions, see README.md"
echo



