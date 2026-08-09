#!/usr/bin/env python3
"""
Start File Organizer server on an available port.
Does NOT start a GUI window - pure API server only.

Searches upward from this script's location to find the app root.
"""

import os
import sys
import subprocess
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Skill structure: /path/to/SoftwareOrganizer/scripts/start-server.py
# App root: /path/to/SoftwareOrganizer/ (two levels up from scripts/)

APP_ROOT = os.environ.get("SOFTWARE_ORGANIZER_APP_DIR")
if not APP_ROOT:
    APP_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
VENV_PYTHON = os.path.join(APP_ROOT, ".venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable
sys.path.insert(0, os.path.join(_SCRIPT_DIR, "..", "src"))

from api_client import _is_file_organizer_server, find_server_port  # noqa: E402

SERVER_PORT, is_existing = find_server_port()

if is_existing:
    print(f"Server already running on port {SERVER_PORT}")
    sys.exit(0)

server_py = os.path.join(APP_ROOT, "src", "server.py")
if not os.path.exists(server_py):
    print(f"ERROR: server.py not found at {server_py}")
    sys.exit(1)

env = os.environ.copy()
env["PYTHONPATH"] = os.path.join(APP_ROOT, "src")

log_dir = os.path.join(os.path.expanduser("~"), ".software_organizer")
os.makedirs(log_dir, mode=0o700, exist_ok=True)
os.chmod(log_dir, 0o700)
log_path = os.path.join(log_dir, "skill-server.log")
with open(log_path, "a", encoding="utf-8") as log_file:
    os.chmod(log_path, 0o600)
    proc = subprocess.Popen(
        [
            VENV_PYTHON,
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(SERVER_PORT),
        ],
        cwd=APP_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

for _ in range(20):
    if _is_file_organizer_server(SERVER_PORT):
        print(f"Server started on port {SERVER_PORT} (PID {proc.pid})")
        sys.exit(0)
    if proc.poll() is not None:
        break
    time.sleep(0.5)

print("ERROR: Server failed to start")
if proc.poll() is None:
    proc.kill()
sys.exit(1)
