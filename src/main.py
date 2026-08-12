# -*- coding: utf-8 -*-
"""
File Organizer Main Entry Point
Responsible for starting the backend API service and loading the GUI window.
"""

import os
import sys
import threading
import time
import socket
import logging
from logging.handlers import RotatingFileHandler
import json
import importlib
import locale
import platform
import re
import subprocess
import urllib.request
import urllib.parse

try:
    import webview
except ImportError:
    print("Error: pywebview not installed. Please run: pip install pywebview")
    sys.exit(1)

def _create_private_rotating_log_handler(log_dir: str) -> RotatingFileHandler:
    os.makedirs(log_dir, exist_ok=True)
    os.chmod(log_dir, 0o700)
    log_path = os.path.join(log_dir, "app.log")
    handler = RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    os.chmod(log_path, 0o600)
    return handler


# Configure logging
if getattr(sys, "frozen", False):
    log_handler = _create_private_rotating_log_handler(
        os.path.join(os.path.expanduser("~"), ".software_organizer")
    )
    logging.basicConfig(
        handlers=[log_handler],
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
else:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Import Server application
# Note: Path handling is critical when running as a frozen PyInstaller app on macOS.
# We ensure the 'src' directory is in sys.path.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from server import app
except ImportError as e:
    logger.error(f"Failed to import server module: {e}")
    # Explicitly attempt to import using absolute path
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    if src_path not in sys.path:
        sys.path.append(src_path)
    try:
        from server import app
    except ImportError as e2:
        logger.critical(f"Secondary import attempt failed: {e2}")
        sys.exit(1)

def is_port_in_use(port: int) -> bool:
    """Check if a port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def check_if_it_is_me(port: int) -> bool:
    """Check if the service running on the port is File Organizer."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health")
        with urllib.request.urlopen(req, timeout=1) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data == {"app": "file-organizer", "status": "ok"}
    except Exception:
        pass
    return False


def get_server_port(start_port=18001, max_port=18050):
    """Find an available port or reuse if already running."""
    for port in range(start_port, max_port + 1):
        if not is_port_in_use(port):
            return port, False
        if check_if_it_is_me(port):
            return port, True
    raise RuntimeError(f"No available local port in {start_port}-{max_port}")


def wait_for_server(port: int, timeout: float = 10) -> bool:
    """Wait until the local API is ready instead of relying on a fixed delay."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check_if_it_is_me(port):
            return True
        time.sleep(0.1)
    return False


def _macos_preferred_locale() -> str | None:
    """Read macOS's ordered language preference, independent of C.UTF-8."""
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/bin/defaults", "read", "-g", "AppleLanguages"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    matches = re.findall(r'"([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)*)"', result.stdout)
    return matches[0] if matches else None


def _qt_system_locale() -> str | None:
    """Use an installed Qt binding as a cross-platform locale fallback."""
    for module_name in ("PySide6.QtCore", "PyQt6.QtCore", "PyQt5.QtCore"):
        try:
            qt_core = importlib.import_module(module_name)
            value = qt_core.QLocale.system().name()
        except (ImportError, AttributeError, RuntimeError):
            continue
        if value and value not in {"C", "POSIX", "en_POSIX"}:
            return value
    return None


def detect_system_locale() -> str:
    """Return the best available UI locale without trusting C.UTF-8 as a language."""
    for value in (_macos_preferred_locale(), _qt_system_locale()):
        if value:
            return value
    for value in (
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
        locale.getlocale()[0],
    ):
        if value:
            return value
    return "en-US"


def start_server(port: int):
    """Start the Uvicorn server."""
    import uvicorn

    try:
        # Use localhost (127.0.0.1) for local access.
        # log_level="error" reduces console noise.
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
    except Exception as e:
        logger.error(f"Server start failed: {e}")


def main():
    logger.info("File Organizer is starting...")

    server_port, is_me = get_server_port()

    # 1. Start API Server
    if not is_me:
        t = threading.Thread(target=start_server, args=(server_port,))
        t.daemon = True
        t.start()
        if not wait_for_server(server_port):
            raise RuntimeError("File Organizer backend failed to start")
    else:
        logger.info(f"Port {server_port} is in use by us; assuming server is already running.")

    # 2. Start WebView window
    logger.info("Starting GUI window...")

    # Determine debug mode based on frozen status
    debug = not getattr(sys, "frozen", False)

    _window = webview.create_window(
        "File Organizer Pro",
        f"http://127.0.0.1:{server_port}/?{urllib.parse.urlencode({'locale': detect_system_locale()})}",
        width=1200,
        height=800,
        resizable=True,
        text_select=True,
    )

    webview.start(debug=debug)


if __name__ == "__main__":
    main()
