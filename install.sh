#!/bin/bash
set -e

echo "========================================"
echo "  IRIS v1 Installer"
echo "========================================"

OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then OS="macos"
elif [[ "$OSTYPE" == "linux-android"* ]]; then OS="termux"
fi

echo "Detected OS: ${OS}"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    echo "Python ${PYTHON_VERSION} found"
else
    echo "Error: Python 3 not found"
    exit 1
fi

echo "Installing system dependencies..."
if [[ "$OS" == "linux" ]]; then
    sudo apt-get update
    sudo apt-get install -y python3-dev python3-pip python3-venv git curl ffmpeg \
        libsm6 libxext6 libgl1-mesa-glx tesseract-ocr libtesseract-dev \
        poppler-utils build-essential redis-server
elif [[ "$OS" == "macos" ]]; then
    if ! command -v brew &> /dev/null; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python@3.11 git ffmpeg tesseract poppler redis
elif [[ "$OS" == "termux" ]]; then
    pkg update
    pkg install -y python git ffmpeg libtesseract tesseract poppler build-essential redis
fi

echo "Setting up virtual environment..."
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Creating directories..."
mkdir -p \
    data/{experiences,iris_learnings,iris_knowledge,iris_self,uploads,vector_db,backups,sandbox,calendar,notes,projects,memory} \
    outputs/{images,audio,video,3d,motion,science} \
    models/{text,image,audio,video,3d,motion,robotics,science} \
    logs

if [[ ! -f ".env" ]]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env with your credentials"
fi

echo ""
echo "========================================"
echo "  IRIS v1 installed successfully!"
echo "========================================"
echo "Next steps:"
echo "  1. Edit .env with your credentials"
echo "  2. source venv/bin/activate && python app.py"
echo "  3. Open: http://localhost:5000"
echo ""
