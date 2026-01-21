#!/bin/bash
# Ubuntu Task Manager (UTM) Reinstall Script

set -e

# Determine script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== Ubuntu Task Manager (UTM) - Reinstallation ==="
echo "This script will delete the current virtual environment and reinstall it."
echo "Configuration (config/config.yaml) will NOT be affected."
echo

read -p "Reinstall Ubuntu Task Manager (UTM)? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo
echo "Stopping service (if running)..."
if systemctl is-active utm.service 2>/dev/null; then
    sudo systemctl stop utm.service
    echo "Service stopped."
fi

echo "Removing old venv..."
rm -rf venv

echo "Starting installation..."
./scripts/install.sh

echo
echo "=== Reinstallation complete! ==="
echo

# Offer to restart service
if systemctl is-enabled utm.service 2>/dev/null; then
    read -p "Start utm service? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl start utm.service
        echo "Service started."
    fi
fi
