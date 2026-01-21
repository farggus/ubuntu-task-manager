#!/bin/bash
# Ubuntu Task Manager (UTM) Quick Start Script

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./scripts/install.sh"
    exit 1
fi

# Activate and run
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python src/main.py "$@"
