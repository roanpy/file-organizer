#!/usr/bin/env python3
"""
Check if File Organizer server is running.
"""

import sys

sys.path.insert(0, str(__file__.rsplit("/scripts", 1)[0]) + "/src")

from api_client import find_server_port

port, is_existing = find_server_port()
if is_existing:
    print(f"File Organizer server is running on port {port}")
    sys.exit(0)
else:
    print("No server found on ports 18001-18050")
    print(f"Next available port: {port}")
    sys.exit(1)
