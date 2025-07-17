#!/bin/bash

echo "================================================"
echo "    Shopee API Integration Application"
echo "================================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 tidak ditemukan!"
    echo "Silakan install Python 3.8+ terlebih dahulu."
    exit 1
fi

echo "Checking Python version..."
python3 --version

echo
echo "Checking if virtual environment exists..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo
echo "Activating virtual environment..."
source venv/bin/activate

echo
echo "Installing requirements..."
pip install -r requirements.txt

echo
echo "Checking .env file..."
if [ ! -f ".env" ]; then
    echo "WARNING: File .env tidak ditemukan!"
    echo "Silakan copy .env.example ke .env dan isi konfigurasi yang diperlukan."
    echo
    read -p "Press enter to continue..."
fi

echo
echo "Initializing database..."
python run.py --init-db

echo
echo "Starting Shopee API Application..."
echo "Open browser dan akses: http://localhost:5000"
echo "Press Ctrl+C untuk stop aplikasi"
echo

python run.py