#!/bin/bash
# Start File Organizer Web Server

# Get project root directory (parent of script directory)
SCRIPT_DIR="$(dirname "$0")"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR" || exit 1

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ Virtual environment does not exist, please run:"
    echo "   cd $PROJECT_DIR"
    echo "   python3 -m venv .venv"
    echo "   source .venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

python SoftwareOrganizer-Skill/scripts/start-server.py
