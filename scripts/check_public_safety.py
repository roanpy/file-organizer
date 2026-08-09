#!/usr/bin/env python3
"""Check tracked text files for common public-repository leaks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".bat",
    ".css",
    ".cfg",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".spec",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
PATTERNS = (
    ("provider key", re.compile(
        r"(?:AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9_-]{16,}|hf_[A-Za-z0-9]{16,}|"
        r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})"
    )),
    ("bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE)),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("personal home path", re.compile(r"/Users/(?!xxx(?:/|$)|<[^>]+>(?:/|$))[^\s'\"`<]+")),
    ("volume path", re.compile(r"/Volumes/[A-Za-z0-9._-]+")),
    ("private network address", re.compile(
        r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?![\d.])"
    )),
    ("placeholder reference", re.compile(r"yourusername/BookOrganizer", re.IGNORECASE)),
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / Path(raw) for raw in result.stdout.decode().split("\0") if raw]


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in tracked_files():
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in PATTERNS:
            if pattern.search(text):
                findings.append((label, str(path.relative_to(ROOT))))

    if findings:
        for label, path in findings:
            print(f"FAIL: {label}: {path}")
        return 1

    print("Public safety check passed: no tracked text-file findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
