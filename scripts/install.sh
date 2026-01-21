#!/bin/bash
# Ubuntu Task Manager (UTM) Quick Install Script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== Ubuntu Task Manager (UTM) - Installation ==="
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3: sudo apt install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python found: $(python3 --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
fi

echo "✓ Dependencies installed"
echo

# Check optional dependencies
echo "Checking optional capabilities:"

if command -v docker &> /dev/null; then
    echo "✓ Docker installed - container monitoring available"
else
    echo "⚠ Docker not found - container monitoring unavailable"
fi

if command -v systemctl &> /dev/null; then
    echo "✓ systemd available - service monitoring available"
else
    echo "⚠ systemd not found - service monitoring limited"
fi

echo
echo "=== Installation complete! ==="
echo
echo "To start:"
echo "  source venv/bin/activate"
echo "  export PYTHONPATH=\$PYTHONPATH:\$(pwd)/src"
echo "  python src/main.py"
echo
echo "Or simply:"
echo "  ./scripts/run.sh"
echo
echo "To configure, edit config/config.yaml"
echo
