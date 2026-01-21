#!/bin/bash
# Ubuntu Task Manager (UTM) Uninstall Script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== Ubuntu Task Manager (UTM) - Uninstallation ==="
echo "WARNING: This will remove the virtual environment and temporary files."
echo "Configuration (config/config.yaml) will be preserved."
echo "System service (if any) will be removed."
echo

read -p "Are you sure you want to uninstall Ubuntu Task Manager (UTM)? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo
echo "1. Removing systemd service..."
if systemctl is-enabled utm.service 2>/dev/null; then
    echo "Stopping and disabling service..."
    sudo systemctl stop utm.service
    sudo systemctl disable utm.service
    sudo rm -f /etc/systemd/system/utm.service
    sudo systemctl daemon-reload
    echo "✓ Service removed"
else
    echo "Service not found or inactive."
fi

echo
echo "2. Removing virtual environment..."
rm -rf venv
echo "✓ venv removed"

echo
echo "3. Cleaning cache..."
rm -rf __pycache__
rm -rf src/__pycache__
rm -rf src/*/__pycache__
rm -rf .pytest_cache
echo "✓ Cache cleaned"

echo
echo "Ubuntu Task Manager (UTM) successfully uninstalled!"
echo "To completely remove the directory run: cd .. && rm -rf $(basename "$PROJECT_ROOT")"
echo
