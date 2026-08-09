# -*- coding: utf-8 -*-
"""
Local API Client for File Organizer - zero backend dependency.

All operations run locally via pathlib/shutil/regex.
"""

import os
import re
import json
import socket
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

from config_manager import load_config, get_categories


# ─── Extension → Category Rules ──────────────────────────────────────────────

CATEGORY_RULES: Dict[str, List[str]] = {
    "development": [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
        ".cpp", ".c", ".h", ".hpp", ".swift", ".kt", ".kts", ".rb",
        ".php", ".cs", ".scala", ".r", ".m", ".mm", ".vue", ".svelte",
    ],
    "design": [
        ".psd", ".ai", ".sketch", ".fig", ".xd", ".indd", ".afdesign",
        ".procreate", ".lip", ".csh",
    ],
    "video": [
        ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm",
        ".prproj", ".aep", ".drp", ".fcpxml",
    ],
    "audio": [
        ".mp3", ".wav", ".flac", ".aac", ".aiff", ".ogg", ".m4a",
        ".wma", ".opus",
    ],
    "image": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".webp", ".svg", ".ico", ".icns", ".heic", ".heif", ".raw",
        ".cr2", ".nef", ".arw",
    ],
    "document": [
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md",
        ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".key", ".numbers",
        ".pages", ".epub", ".mobi",
    ],
    "archive": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".dmg", ".pkg", ".deb", ".rpm", ".iso",
    ],
    "app": [
        ".app", ".ipa", ".apk", ".exe", ".msi",
    ],
}

# Build reverse lookup: ext → category
_EXT_MAP: Dict[str, str] = {}
for _cat, _exts in CATEGORY_RULES.items():
    for _ext in _exts:
        _EXT_MAP[_ext.lower()] = _cat


# ─── Utility ─────────────────────────────────────────────────────────────────

def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _classify_by_ext(filename: str) -> Optional[str]:
    _, ext = os.path.splitext(filename)
    return _EXT_MAP.get(ext.lower())


def _classify_by_config(filename: str, categories: Dict[str, Any]) -> Optional[str]:
    """Classify using user-defined categories from config."""
    _, ext = os.path.splitext(filename)
    for cat_id, info in categories.items():
        if ext.lower() in [f.lower() for f in info.get("formats", [])]:
            return cat_id
    return None


def _is_path_within(path: str, root: str) -> bool:
    if not path or not root or not os.path.isabs(path) or not os.path.isabs(root):
        return False
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except (OSError, ValueError):
        return False


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        return connection.connect_ex(("127.0.0.1", port)) == 0


def _is_file_organizer_server(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/health", timeout=1
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data == {"app": "file-organizer", "status": "ok"}
    except Exception:
        return False


def find_server_port(
    start_port: int = 18001, max_port: int = 18050
) -> tuple[int, bool]:
    """Return an available port or an existing File Organizer backend."""
    for port in range(start_port, max_port + 1):
        if not _port_in_use(port):
            return port, False
        if _is_file_organizer_server(port):
            return port, True
    raise RuntimeError(f"No available local port in {start_port}-{max_port}")


def _target_roots(config: Dict[str, Any]) -> List[str]:
    roots = [
        info.get("target_dir", "")
        for info in get_categories(config).values()
        if info.get("target_dir")
    ]
    if config.get("target_dir"):
        roots.append(config["target_dir"])
    return roots


def _extract_version(filename: str) -> Optional[str]:
    """Extract version number from filename."""
    stem = Path(filename).stem
    date_match = re.search(
        r"((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?([0-2]\d|3[01])", stem
    )
    if date_match:
        return ".".join(date_match.groups())
    # Match patterns like v1.2.3, 1.2.3, 1.0, etc.
    m = re.search(r'(?:v|V)?(\d+\.\d+(?:\.\d+)*(?:[-_][\w]+)?)', stem)
    return m.group(1) if m else None


def _group_base_name(filename: str) -> str:
    """Extract a normalized base name for duplicate grouping."""
    stem = Path(filename).stem.lower()
    # Remove common version patterns, architecture tags, etc.
    name = re.sub(r'[-_]?v?\d+(\.\d+)+[-_]?[\w.-]*$', '', stem)
    name = re.sub(r'[-_]?(x86|x64|arm64|amd64|universal|mac|win|linux|intel)[-_]?.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[-_.]+$', '', name)
    return name.strip(' -._')


def _artifact_variant(filename: str) -> str:
    """Separate package variants that must never be treated as old versions."""
    stem = Path(filename).stem.lower()
    variants = []
    patterns = (
        ("language-pack", r"(?:^|[^a-z0-9])(?:lang(?:uage)?[ _-]?pack|help[ _-]?pack)(?:[^a-z0-9]|$)"),
        ("patch", r"(?:^|[^a-z0-9])(?:patch|crack|keygen|activation)(?:[^a-z0-9]|$)"),
        ("arm64", r"(?:^|[^a-z0-9])(?:arm64|aarch64|apple[ _-]?silicon)(?:[^a-z0-9]|$)"),
        ("intel", r"(?:^|[^a-z0-9])(?:x86[ _-]?64|x64|amd64|intel)(?:[^a-z0-9]|$)"),
        ("universal", r"(?:^|[^a-z0-9])universal(?:[^a-z0-9]|$)"),
    )
    for variant, pattern in patterns:
        if re.search(pattern, stem):
            variants.append(variant)
    return "+".join(variants) or "main"


def _group_identity(file_info: Dict[str, Any]) -> tuple[str, str]:
    filename = file_info.get("filename", "")
    base = _group_base_name(filename) or Path(filename).stem.lower()
    generic_names = {
        "autoupdate", "download", "install", "installer", "launcher",
        "setup", "uninstall", "update", "updater",
    }
    parent = ""
    if base in generic_names:
        parent = os.path.realpath(
            file_info.get("parent_dir") or os.path.dirname(file_info.get("path", ""))
        )
    return f"{base}|{_artifact_variant(filename)}|{parent}", base


def _version_key(version: Optional[str]) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version or ""))


# ─── Core Functions ──────────────────────────────────────────────────────────

def scan_directory(source_path: str, extensions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Scan a directory and return file list with metadata."""
    source = Path(source_path)
    if not source.is_dir():
        return {"software": [], "category_counts": {}, "error": f"Directory not found: {source_path}"}

    config = load_config()
    categories = get_categories(config)

    software = []
    ext_lower = [e.lower() for e in extensions] if extensions else None

    for item in source.iterdir():
        if not item.is_file():
            continue
        if item.name.startswith('.'):
            continue

        _, ext = os.path.splitext(item.name)
        if ext_lower and ext.lower() not in ext_lower:
            continue

        # Classify: config rules first, then built-in rules
        category = _classify_by_config(item.name, categories)
        category_name = None
        if category:
            category_name = categories.get(category, {}).get("name", category)
        else:
            # Try built-in rules
            builtin = _classify_by_ext(item.name)
            if builtin:
                category = builtin
                category_name = builtin.capitalize()

        stat = item.stat()
        software.append({
            "filename": item.name,
            "path": str(item),
            "size": stat.st_size,
            "size_formatted": _format_size(stat.st_size),
            "extension": ext.lower(),
            "category": category or "",
            "category_name": category_name or "",
            "version": _extract_version(item.name),
            "modified": stat.st_mtime,
            "location": "source",
        })

    # Build category counts
    counts: Dict[str, Any] = {}
    for s in software:
        cat = s["category"] or "unclassified"
        if cat not in counts:
            name = s.get("category_name") or cat
            counts[cat] = {"name": name, "count": 0}
        counts[cat]["count"] += 1

    return {
        "software": sorted(software, key=lambda x: x["filename"].lower()),
        "category_counts": counts,
    }


def analyze_software(files: List[Dict], config: Optional[Dict] = None) -> Dict[str, Any]:
    """Analyze files: classify and group by base name."""
    if config is None:
        config = load_config()

    categories = get_categories(config)

    # Enrich with categories
    for f in files:
        if not f.get("category"):
            cat = _classify_by_config(f.get("filename", ""), categories)
            if cat:
                f["category"] = cat
                f["category_name"] = categories.get(cat, {}).get("name", cat)
            else:
                builtin = _classify_by_ext(f.get("filename", ""))
                if builtin:
                    f["category"] = builtin
                    f["category_name"] = builtin.capitalize()

    # Group by base name
    groups: Dict[str, Dict[str, Any]] = {}
    for f in files:
        identity, base = _group_identity(f)
        group = groups.setdefault(identity, {"software_name": base, "files": []})
        group["files"].append(f)

    return {
        "groups": sorted(groups.values(), key=lambda group: group["software_name"]),
    }


def analyze_duplicates(files: List[Dict]) -> Dict[str, Any]:
    """Find duplicate software groups by normalized name."""
    groups: Dict[str, Dict[str, Any]] = {}
    for f in files:
        identity, base = _group_identity(f)
        group = groups.setdefault(identity, {"software_name": base, "files": []})
        group["files"].append(f)

    # Only keep groups with >1 file
    dup_groups = []
    for group in sorted(groups.values(), key=lambda item: item["software_name"]):
        members = group["files"]
        if len(members) > 1:
            best_idx = max(
                range(len(members)),
                key=lambda index: (
                    bool(members[index].get("version")),
                    _version_key(members[index].get("version")),
                    members[index].get("modified", 0) or 0,
                ),
            )
            for i, m in enumerate(members):
                m["is_kept"] = (i == best_idx)
            dup_groups.append(group)

    return {"groups": dup_groups}


def transfer_file(file_path: str, dest_folder: str, overwrite: bool = False) -> Dict[str, Any]:
    """Transfer a single file to destination."""
    src = Path(file_path)
    dst = Path(dest_folder)
    config = load_config()

    if not src.is_file():
        return {"success": False, "error": f"Source not found: {file_path}"}
    if not _is_path_within(str(src), config.get("source_dir", "")):
        return {"success": False, "error": "Source is outside the configured source directory"}
    if not any(_is_path_within(str(dst), root) for root in _target_roots(config)):
        return {"success": False, "error": "Destination is outside configured target directories"}

    temp_path = None
    try:
        dst.mkdir(parents=True, exist_ok=True)
        target = dst / src.name
        if target.exists() and os.path.samefile(src, target):
            return {"success": True, "destination": str(target), "unchanged": True}
        if target.exists() and not overwrite:
            return {"success": False, "error": f"File already exists: {target}"}
        if target.exists():
            fd, temp_path = tempfile.mkstemp(prefix=".file-organizer-", dir=dst)
            os.close(fd)
            shutil.copy2(src, temp_path)
            os.replace(temp_path, target)
            temp_path = None
            src.unlink()
        else:
            shutil.move(str(src), str(target))
        return {"success": True, "destination": str(target)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def transfer(files: List[str], destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Transfer multiple files. Returns summary."""
    success, failed = [], []
    for fp in files:
        r = transfer_file(fp, destination, overwrite)
        if r.get("success"):
            success.append(fp)
        else:
            failed.append({"path": fp, "error": r.get("error", "")})
    return {"success": success, "failed": failed}


def delete_file(file_path: str) -> Dict[str, Any]:
    """Move a managed target file to macOS Trash."""
    p = Path(file_path)
    if not p.is_file():
        return {"success": False, "error": f"File not found: {file_path}"}
    if not any(_is_path_within(str(p), root) for root in _target_roots(load_config())):
        return {"success": False, "error": "File is outside configured target directories"}

    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                'tell application "Finder" to delete POSIX file (item 1 of argv)',
                "-e",
                "end run",
                file_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "method": "trash"}
        return {"success": False, "error": result.stderr.strip() or "Failed to move file to Trash"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_files(files: List[str]) -> Dict[str, Any]:
    """Delete multiple files. Returns summary."""
    success, failed = [], []
    for fp in files:
        r = delete_file(fp)
        if r.get("success"):
            success.append(fp)
        else:
            failed.append({"path": fp, "error": r.get("error", "")})
    return {"success": success, "failed": failed}


# ─── Target Directory Scanning ───────────────────────────────────────────────

def scan_target_directories(target_dir: str, categories: Dict[str, Any]) -> Dict[str, Any]:
    """Scan all category target directories."""
    target = Path(target_dir)
    if not target.is_dir():
        return {"categories": {}, "total": 0}

    result = {}
    total = 0

    for cat_id, info in categories.items():
        cat_dir = info.get("target_dir", "")
        if cat_dir:
            cat_path = Path(cat_dir)
        else:
            cat_path = target / cat_id

        if not cat_path.is_dir():
            result[cat_id] = {"name": info.get("name", cat_id), "files": [], "count": 0}
            continue

        files = []
        for item in cat_path.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                stat = item.stat()
                files.append({
                    "filename": item.name,
                    "path": str(item),
                    "size": stat.st_size,
                    "size_formatted": _format_size(stat.st_size),
                    "extension": os.path.splitext(item.name)[1].lower(),
                    "category": cat_id,
                    "category_name": info.get("name", cat_id),
                    "version": _extract_version(item.name),
                    "modified": stat.st_mtime,
                    "location": "target",
                })

        files.sort(key=lambda x: x["filename"].lower())
        result[cat_id] = {
            "name": info.get("name", cat_id),
            "files": files,
            "count": len(files),
        }
        total += len(files)

    return {"categories": result, "total": total}


# ─── Config Accessors (backward compatible) ─────────────────────────────────

def get_config() -> Dict[str, Any]:
    return load_config()


def get_ai_config() -> Dict[str, Any]:
    """Return minimal AI config (all local now)."""
    return {"engine": "local", "use_ai": False}


def get_categories_api() -> Dict[str, Any]:
    config = load_config()
    return get_categories(config)
