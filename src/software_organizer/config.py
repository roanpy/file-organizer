# -*- coding: utf-8 -*-
"""
Configuration Management Module - Handles application configuration and history.

Contains:
- Directory path constants
- Configuration loading/saving
- AI configuration management
- History log management
- Software category management
"""

import os
import json
import copy
import re
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# ==============================================================================
# Global Constants
# ==============================================================================

APP_DIR = os.path.join(os.path.expanduser("~"), ".software_organizer")
os.makedirs(APP_DIR, mode=0o700, exist_ok=True)
try:
    os.chmod(APP_DIR, 0o700)
except OSError:
    pass

CONFIG_FILE = os.path.join(APP_DIR, "software_organizer_config.json")
HISTORY_FILE = os.path.join(APP_DIR, "software_organizer_history.json")
AI_CONFIG_FILE = CONFIG_FILE

# Default file category configuration
DEFAULT_CATEGORIES = {
    "general": {
        "name": "通用格式 (Universal)",
        "formats": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "target_dir": "",
        "cross_format_match": False,
    },
    "documents": {
        "name": "文档资料",
        "formats": [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".txt",
            ".md",
            ".epub",
        ],
        "target_dir": "",
        "cross_format_match": False,
    },
    "mac": {
        "name": "Mac",
        "formats": [".dmg", ".pkg", ".zip", ".7z", ".rar"],
        "target_dir": "",
        "cross_format_match": True,
    },
    "ios": {
        "name": "iOS",
        "formats": [".ipa"],
        "target_dir": "",
        "cross_format_match": False,
    },
    "windows": {
        "name": "Windows",
        "formats": [".exe", ".msi", ".zip", ".7z", ".rar"],
        "target_dir": "",
        "cross_format_match": True,
    },
}

CATEGORY_ID_PATTERN = re.compile(r"^[a-z0-9]+$")


def is_valid_category_id(cat_id: str) -> bool:
    return bool(CATEGORY_ID_PATTERN.fullmatch(cat_id or ""))

# AI Core Rules
DEFAULT_CORE_RULES = """You are a software version identification expert. Your task is to analyze software names and identify different versions of the same software.

**Core Principles**
1. Software Name Matching: Ignore differences in version numbers, build numbers, etc., to identify the core software name.
2. Version Extraction: Extract version numbers from filenames (e.g., v1.2.3, 1.2.3, Build 123).
3. Category Identification: Identify software category based on file extension.

**Output Requirements**
1. Return in JSON format.
2. Identify software name, version number, and category type.
3. Sort by latest version."""


# ==============================================================================
# Configuration Management Functions
# ==============================================================================


def get_default_config() -> Dict[str, Any]:
    """Get the default configuration."""
    return {
        "source_dir": "",
        "categories": copy.deepcopy(DEFAULT_CATEGORIES),
        "gemini": {},
        "deepseek": {},
        "ollama": {},
        "custom_providers": {},
        "ai_config": get_default_ai_config(),
        "current_engine": "gemini",
        "use_ai": False,
    }


def write_json_file(path: str, data: Any) -> None:
    """Atomically write private application state as UTF-8 JSON."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".file-organizer-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def ensure_private_file(path: str) -> None:
    """Restrict an existing application state file to the current user."""
    if not os.path.exists(path):
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


PRIVATE_STATE_FILENAMES = (
    "software_organizer_config.json",
    "software_organizer_history.json",
    "keep_rules.json",
    "retention_rules.json",
    "ai_recommendations.json",
    "software_organizer.db",
    "app.log",
    "main.log",
    "server.log",
    "skill-server.log",
)


def ensure_private_runtime_state(app_dir: str = APP_DIR) -> None:
    """Restrict existing configuration, database, and log files to the owner."""
    for state_filename in PRIVATE_STATE_FILENAMES:
        ensure_private_file(os.path.join(app_dir, state_filename))


ensure_private_runtime_state()


def migrate_old_config(config: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """
    Migrate legacy configuration to the new 'categories' structure.

    Moves mac_target_dir, ios_target_dir, and file_formats into categories.
    """
    migrated = False

    # Create default categories if none exist
    if "categories" not in config:
        config["categories"] = copy.deepcopy(DEFAULT_CATEGORIES)
        migrated = True

    # Migrate mac_target_dir
    if "mac_target_dir" in config and config["mac_target_dir"]:
        if "mac" in config["categories"]:
            config["categories"]["mac"]["target_dir"] = config["mac_target_dir"]
        del config["mac_target_dir"]
        migrated = True

    # Migrate ios_target_dir
    if "ios_target_dir" in config and config["ios_target_dir"]:
        if "ios" in config["categories"]:
            config["categories"]["ios"]["target_dir"] = config["ios_target_dir"]
        del config["ios_target_dir"]
        migrated = True

    # Migrate file_formats
    if "file_formats" in config:
        for cat_id, formats in config["file_formats"].items():
            if cat_id in config["categories"]:
                config["categories"][cat_id]["formats"] = formats
        del config["file_formats"]
        migrated = True

    return config, migrated


def load_config() -> Dict[str, Any]:
    """Load the main configuration file."""
    config = get_default_config()

    if os.path.exists(CONFIG_FILE):
        ensure_private_file(CONFIG_FILE)
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
                # Merge saved config into default config
                for key, value in saved_config.items():
                    if (
                        isinstance(value, dict)
                        and key in config
                        and isinstance(config[key], dict)
                    ):
                        config[key].update(value)
                    else:
                        config[key] = value
        except Exception:
            pass

    # Migrate legacy config
    config, migrated = migrate_old_config(config)
    if migrated:
        save_config(config)

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save the main configuration file."""
    write_json_file(CONFIG_FILE, config)


# ==============================================================================
# Software Category Management
# ==============================================================================


def get_categories() -> Dict[str, Dict[str, Any]]:
    """Retrieve all software categories."""
    config = load_config()
    return config.get("categories", DEFAULT_CATEGORIES)


def get_category_by_extension(extension: str) -> Optional[str]:
    """Get Category ID based on file extension."""
    categories = get_categories()
    ext_lower = extension.lower()
    for cat_id, cat_info in categories.items():
        if ext_lower in [f.lower() for f in cat_info.get("formats", [])]:
            return cat_id
    return None


def get_all_formats() -> List[str]:
    """Retrieve all configured file formats."""
    categories = get_categories()
    all_formats = []
    for cat_info in categories.values():
        all_formats.extend(cat_info.get("formats", []))
    return list(set(all_formats))


def check_format_conflict(
    new_formats: List[str], exclude_category: str = None
) -> List[str]:
    """
    Check for file format conflicts among categories.

    Returns a list of formats that conflict with other categories.
    """
    categories = get_categories()
    conflicts = []

    # Get format list from the 'general' category
    general_formats = []
    if "general" in categories:
        general_formats = [f.lower() for f in categories["general"].get("formats", [])]

    for cat_id, cat_info in categories.items():
        if cat_id == exclude_category:
            continue
        # Skip 'general' category conflicts (allow overrides)
        if cat_id == "general" or exclude_category == "general":
            continue

        existing_formats = [f.lower() for f in cat_info.get("formats", [])]
        for fmt in new_formats:
            fmt_lower = fmt.lower()
            # If the format exists in 'general', allow it to be overridden elsewhere
            if fmt_lower in general_formats:
                continue

            if fmt_lower in existing_formats:
                conflicts.append(fmt)

    return conflicts


def add_category(cat_id: str, name: str, formats: List[str]) -> Dict[str, Any]:
    """Add a new software category."""
    config = load_config()

    if not is_valid_category_id(cat_id):
        return {
            "success": False,
            "error": "Category ID must contain only lowercase letters and numbers.",
        }

    # Check if ID already exists
    if cat_id in config["categories"]:
        return {"success": False, "error": f"Category ID '{cat_id}' already exists."}

    # Check for format conflicts
    conflicts = check_format_conflict(formats)
    if conflicts:
        return {"success": False, "error": f"Format conflict: {', '.join(conflicts)}"}

    config["categories"][cat_id] = {
        "name": name,
        "formats": formats,
        "target_dir": "",
        "cross_format_match": False,
    }
    save_config(config)
    return {"success": True}


def update_category(
    cat_id: str,
    name: str = None,
    formats: List[str] = None,
    target_dir: str = None,
    cross_format_match: bool = None,
) -> Dict[str, Any]:
    """Update an existing software category."""
    config = load_config()

    if cat_id not in config["categories"]:
        return {"success": False, "error": f"Category '{cat_id}' does not exist."}

    # Check for format conflicts (excluding current category)
    if formats is not None:
        conflicts = check_format_conflict(formats, exclude_category=cat_id)
        if conflicts:
            return {
                "success": False,
                "error": f"Format conflict: {', '.join(conflicts)}",
            }
        config["categories"][cat_id]["formats"] = formats

    if name is not None:
        config["categories"][cat_id]["name"] = name

    if target_dir is not None:
        config["categories"][cat_id]["target_dir"] = target_dir

    if cross_format_match is not None:
        config["categories"][cat_id]["cross_format_match"] = cross_format_match

    save_config(config)
    return {"success": True}


def delete_category(cat_id: str) -> Dict[str, Any]:
    """Delete a software category."""
    config = load_config()

    if cat_id not in config["categories"]:
        return {"success": False, "error": f"Category '{cat_id}' does not exist."}

    if cat_id == "general":
        return {"success": False, "error": "The 'general' category cannot be deleted."}

    del config["categories"][cat_id]
    save_config(config)
    return {"success": True}


def restore_category_defaults(cat_id: str) -> Dict[str, Any]:
    """Restore a category to its default settings."""
    if cat_id not in DEFAULT_CATEGORIES:
        return {"success": False, "error": "No default settings for this category."}

    config = load_config()

    # Persist the current target directory if possible
    current_target = config["categories"].get(cat_id, {}).get("target_dir", "")

    default_info = DEFAULT_CATEGORIES[cat_id].copy()
    config["categories"][cat_id] = default_info
    # Restore user-set directory (if any)
    config["categories"][cat_id]["target_dir"] = current_target

    save_config(config)
    return {"success": True}


# ==============================================================================
# AI Configuration Management
# ==============================================================================


def get_default_ai_config() -> Dict[str, Any]:
    """Get default AI configuration."""
    return {
        "core_rules": {"enabled": True, "content": DEFAULT_CORE_RULES},
        "analysis_settings": {
            "version_detection": True,
            "smart_grouping": True,
            "path_suggestion": True,
        },
    }


def load_ai_config() -> Dict[str, Any]:
    """Load AI configuration."""
    config = load_config()
    return config.get("ai_config", get_default_ai_config())


def save_ai_config(ai_config: Dict[str, Any]) -> None:
    """Save AI configuration."""
    config = load_config()
    config["ai_config"] = ai_config
    save_config(config)


# ==============================================================================
# History Management
# ==============================================================================


def load_history() -> Dict[str, Any]:
    """Load operation history."""
    if os.path.exists(HISTORY_FILE):
        ensure_private_file(HISTORY_FILE)
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history: Dict[str, Any]) -> None:
    """Save operation history."""
    write_json_file(HISTORY_FILE, history)


def save_history_item(
    filename: str, status: str, details: Optional[Dict] = None
) -> None:
    """Save a single history entry."""
    history = load_history()
    history[filename] = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": details or {},
    }
    save_history(history)


def get_software_status(filename: str) -> str:
    """Retrieve application processing status."""
    history = load_history()
    return history.get(filename, {}).get("status", "pending")


def get_historical_transfers(days_range: int = 30) -> List[Dict[str, Any]]:
    """Retrieve historical transfer records within a date range."""
    history = load_history()
    cutoff_date = datetime.now() - timedelta(days=days_range)

    recent_transfers = []
    for filename, record in history.items():
        if record.get("status") == "transferred":
            try:
                record_date = datetime.fromisoformat(record["timestamp"])
                if record_date >= cutoff_date:
                    recent_transfers.append(
                        {
                            "filename": filename,
                            "destination": record.get("details", {}).get(
                                "destination", ""
                            ),
                            "timestamp": record["timestamp"],
                        }
                    )
            except Exception:
                pass

    return recent_transfers
