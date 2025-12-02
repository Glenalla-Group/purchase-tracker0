@echo off
echo ========================================
echo Purchase Tracker Backend - Quick Start
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/
    pause
    exit /b 1
)

echo [1/6] Checking Python version...
python --version

echo.
echo [2/6] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo Virtual environment created successfully
) else (
    echo Virtual environment already exists
)

echo.
echo [3/6] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [4/6] Installing dependencies...
pip install --quiet --upgrade pip
pip install -r requirements.txt

echo.
echo [5/6] Checking setup...
python test_setup.py

echo.
echo [6/6] Gmail Authentication...
echo.
if not exist "credentials.json" (
    echo ERROR: credentials.json not found!
    echo.
    echo Please download OAuth credentials:
    echo 1. Go to https://console.cloud.google.com/apis/credentials
    echo 2. Create OAuth Client ID - Desktop app
    echo 3. Download JSON and save as credentials.json
    echo.
    pause
    exit /b 1
)

if exist "token.json" (
    echo Token already exists. Skipping authentication.
) else (
    echo Starting Gmail authentication...
    echo A browser window will open for authentication.
    echo.
    python authenticate.py
    if errorlevel 1 (
        echo.
        echo Authentication failed. Please check the error above.
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To start the server, run:
echo     python run.py
echo.
echo Or just press Enter to start now...
pause
python run.py
