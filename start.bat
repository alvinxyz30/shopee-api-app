@echo off
echo ================================================
echo    Shopee API Integration Application
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python tidak ditemukan!
    echo Silakan install Python 3.8+ terlebih dahulu.
    pause
    exit /b 1
)

echo Checking Python version...
python --version

echo.
echo Checking if virtual environment exists...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing requirements...
pip install -r requirements.txt

echo.
echo Checking .env file...
if not exist ".env" (
    echo WARNING: File .env tidak ditemukan!
    echo Silakan copy .env.example ke .env dan isi konfigurasi yang diperlukan.
    echo.
    pause
)

echo.
echo Initializing database...
python run.py --init-db

echo.
echo Starting Shopee API Application...
echo Open browser dan akses: http://localhost:5000
echo Press Ctrl+C untuk stop aplikasi
echo.

python run.py

pause