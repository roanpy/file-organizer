# -*- coding: utf-8 -*-
"""
Persistence Module - Handles storage for user preferences and AI recommendations.

Contains:
- Loading and saving of "Keep" rules (preferences for keeping target files).
- Support for storage by file path, distinguishing between different versions of the same software.
- Caching of AI recommendations.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from .config import APP_DIR, ensure_private_file, write_json_file

DATA_DIR = APP_DIR

KEEP_RULES_FILE = os.path.join(DATA_DIR, "keep_rules.json")
RETENTION_RULES_FILE = os.path.join(DATA_DIR, "retention_rules.json")


_keep_rules_cache = None
_retention_rules_cache = None


def _default_retention_rules() -> Dict[str, Any]:
    """Default cleanup protection policy."""
    return {
        "global_keep_latest": 1,
        "software_policies": {},
        "protected_directories": [],
        "protected_keywords": [],
    }


def _version_key(value: Optional[str]) -> tuple:
    if not value:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", str(value)))


def _retention_key(value: str) -> str:
    from .file_ops import normalize_software_name

    return normalize_software_name(value or "")


def _is_under_directory(path: str, directory: str) -> bool:
    if not path or not directory:
        return False

    abs_path = os.path.abspath(path)
    abs_dir = os.path.abspath(os.path.expanduser(directory))
    return abs_path == abs_dir or abs_path.startswith(abs_dir + os.sep)


def load_keep_rules() -> Dict[str, bool]:
    """
    Load "Keep" rules. Uses in-memory cache for performance.

    Returns:
        Rules dictionary { "file_path": true } or legacy format { "SoftwareName": true }.
    """
    global _keep_rules_cache
    if _keep_rules_cache is not None:
        return _keep_rules_cache

    if not os.path.exists(KEEP_RULES_FILE):
        _keep_rules_cache = {}
        return _keep_rules_cache

    try:
        ensure_private_file(KEEP_RULES_FILE)
        with open(KEEP_RULES_FILE, "r", encoding="utf-8") as f:
            _keep_rules_cache = json.load(f)
            return _keep_rules_cache
    except Exception as e:
        print(f"Error loading keep rules: {e}")
        return {}


def save_keep_rule(
    file_path: str, keep: bool, software_name: Optional[str] = None
) -> bool:
    """
    Save a single "Keep" rule (by file path).

    Args:
        file_path: File path (used as unique identifier).
        keep: Whether to keep the file.
        software_name: Software name (optional, for backward compatibility).

    Returns:
        bool: True if successful.
    """
    rules = dict(load_keep_rules())

    # Use file path as the key
    # Note: Save False instead of deleting, to distinguish "not kept" from "not set"
    rules[file_path] = keep
    # Save software name if provided (for backward compatibility)
    if software_name:
        rules[software_name] = keep

    try:
        write_json_file(KEEP_RULES_FILE, rules)

        # Update cache
        global _keep_rules_cache
        _keep_rules_cache = rules

        return True
    except Exception as e:
        print(f"Error saving keep rules: {e}")
        return False


def is_kept(identifier: str) -> bool:
    """
    Check if a file is marked to be kept.

    Args:
        identifier: File path or software name.

    Returns:
        bool: True if kept.
    """
    rules = load_keep_rules()
    return rules.get(identifier, False)


def has_keep_rule(identifier: str) -> bool:
    """
    Check if a 'Keep' rule exists (whether True or False).

    Args:
        identifier: File path or software name.

    Returns:
        bool: True if a rule exists.
    """
    rules = load_keep_rules()
    return identifier in rules


# ==============================================================================
# Retention Policy Persistence
# ==============================================================================


def load_retention_rules() -> Dict[str, Any]:
    """Load structured retention rules used by duplicate cleanup."""
    global _retention_rules_cache
    if _retention_rules_cache is not None:
        return _retention_rules_cache

    defaults = _default_retention_rules()
    if not os.path.exists(RETENTION_RULES_FILE):
        _retention_rules_cache = defaults
        return _retention_rules_cache

    try:
        ensure_private_file(RETENTION_RULES_FILE)
        with open(RETENTION_RULES_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            loaded = {}
        defaults.update(loaded)
        defaults.setdefault("software_policies", {})
        defaults.setdefault("protected_directories", [])
        defaults.setdefault("protected_keywords", [])
        _retention_rules_cache = defaults
        return _retention_rules_cache
    except Exception as e:
        print(f"Error loading retention rules: {e}")
        _retention_rules_cache = defaults
        return _retention_rules_cache


def save_retention_rules(rules: Dict[str, Any]) -> bool:
    """Persist structured retention rules."""
    try:
        write_json_file(RETENTION_RULES_FILE, rules)

        global _retention_rules_cache
        _retention_rules_cache = rules
        return True
    except Exception as e:
        print(f"Error saving retention rules: {e}")
        return False


def save_software_retention_policy(
    software_name: str,
    keep_latest: Optional[int] = None,
    never_delete: Optional[bool] = None,
    reset: bool = False,
) -> Dict[str, Any]:
    """Create, update, or remove a software-level retention policy."""
    key = _retention_key(software_name)
    if not key:
        return {"success": False, "error": "Missing software name"}

    rules = load_retention_rules()
    policies = rules.setdefault("software_policies", {})

    if reset:
        policies.pop(key, None)
        save_retention_rules(rules)
        return {"success": True, "key": key, "policy": None}

    policy = dict(policies.get(key, {}))
    policy["software_name"] = software_name

    if keep_latest is not None:
        policy["keep_latest"] = max(0, int(keep_latest))
    if never_delete is not None:
        policy["never_delete"] = bool(never_delete)

    policies[key] = policy
    if not save_retention_rules(rules):
        return {"success": False, "error": "Failed to save retention policy"}
    return {"success": True, "key": key, "policy": policy}


def annotate_duplicate_retention(
    items: List[Dict[str, Any]], software_name: str
) -> Dict[str, Any]:
    """
    Annotate duplicate items with structured retention decisions.

    Items must already be sorted newest first. The function marks hard protections
    separately from soft default keep recommendations.
    """
    rules = load_retention_rules()
    key = _retention_key(software_name)
    policy = rules.get("software_policies", {}).get(key, {})
    global_keep_latest = int(rules.get("global_keep_latest", 1) or 0)

    for item in items:
        item["retention_key"] = key
        item["retention_protected"] = False
        item["retention_reason"] = ""
        item["retention_source"] = ""
        item["recommended_keep"] = False
        item["recommend_reason"] = ""

    protected_directories = rules.get("protected_directories", []) or []
    protected_keywords = [
        str(keyword).lower()
        for keyword in rules.get("protected_keywords", []) or []
        if str(keyword).strip()
    ]

    def protect(item: Dict[str, Any], source: str, reason: str) -> None:
        item["retention_protected"] = True
        item["retention_source"] = source
        item["retention_reason"] = reason
        item["recommended_keep"] = True
        item["recommend_reason"] = reason

    if policy.get("never_delete"):
        for item in items:
            protect(item, "software_policy", "策略：此分组永不清理")
    else:
        keep_latest = int(policy.get("keep_latest") or 0)
        if keep_latest > 0:
            for item in items[:keep_latest]:
                protect(item, "software_policy", f"策略：保留最近 {keep_latest} 个版本")

        keep_versions = {str(v).lower() for v in policy.get("keep_versions", []) or []}
        keep_keywords = [
            str(keyword).lower()
            for keyword in policy.get("keep_keywords", []) or []
            if str(keyword).strip()
        ]
        for item in items:
            version = str(item.get("version") or "").lower()
            filename = item.get("filename", "").lower()
            name = item.get("name", "").lower()
            if version and version in keep_versions:
                protect(item, "software_policy", f"策略：保留版本 {item.get('version')}")
            elif keep_keywords and any(k in filename or k in name for k in keep_keywords):
                protect(item, "software_policy", "策略：关键词保护")

    for item in items:
        path = item.get("path", "")
        if any(_is_under_directory(path, directory) for directory in protected_directories):
            protect(item, "directory_policy", "策略：目录已排除清理")

        filename = item.get("filename", "").lower()
        name = item.get("name", "").lower()
        if protected_keywords and any(k in filename or k in name for k in protected_keywords):
            protect(item, "keyword_policy", "策略：关键词已排除清理")

    # Soft default: keep newest N files unless a software-level latest policy
    # already owns that decision. Directory/keyword protections should add to
    # the default latest recommendation, not replace it.
    has_latest_policy = bool(policy.get("never_delete")) or int(policy.get("keep_latest") or 0) > 0
    if global_keep_latest > 0 and not has_latest_policy:
        for item in items[:global_keep_latest]:
            if not item.get("recommended_keep"):
                item["recommended_keep"] = True
                item["recommend_reason"] = f"默认：保留最近 {global_keep_latest} 个版本"
                item["retention_source"] = "default_latest"

    protected_count = sum(1 for item in items if item.get("retention_protected"))
    recommended_count = sum(1 for item in items if item.get("recommended_keep"))
    return {
        "retention_key": key,
        "policy": policy,
        "protected_count": protected_count,
        "recommended_count": recommended_count,
        "delete_candidate_count": max(0, len(items) - recommended_count),
    }


# ==============================================================================
# AI Recommendations Persistence
# ==============================================================================

AI_RECOMMENDATIONS_FILE = os.path.join(DATA_DIR, "ai_recommendations.json")


def load_ai_recommendations() -> Dict[str, dict]:
    """
    Load AI recommendation cache.

    Returns:
        dict: {group_hash: {reason, keep_indices, timestamp}}
    """
    if not os.path.exists(AI_RECOMMENDATIONS_FILE):
        return {}

    try:
        ensure_private_file(AI_RECOMMENDATIONS_FILE)
        with open(AI_RECOMMENDATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading AI recommendations: {e}")
        return {}


def save_ai_recommendation(group_hash: str, recommendation: dict) -> bool:
    """
    Save a single AI recommendation.

    Args:
        group_hash: Group hash (Software name + File list hash).
        recommendation: {reason, keep_indices}.

    Returns:
        bool: True if successful.
    """
    import time

    recommendations = load_ai_recommendations()

    # Add timestamp
    recommendation["timestamp"] = int(time.time())
    recommendations[group_hash] = recommendation

    try:
        write_json_file(AI_RECOMMENDATIONS_FILE, recommendations)
        return True
    except Exception as e:
        print(f"Error saving AI recommendation: {e}")
        return False


def save_ai_recommendations_batch(recommendations: Dict[str, dict]) -> bool:
    """
    Save multiple AI recommendations in a batch.

    Args:
        recommendations: {group_hash: {reason, keep_indices}}.

    Returns:
        bool: True if successful.
    """
    import time

    existing = load_ai_recommendations()

    # Merge new recommendations
    timestamp = int(time.time())
    for group_hash, rec in recommendations.items():
        rec["timestamp"] = timestamp
        existing[group_hash] = rec

    try:
        write_json_file(AI_RECOMMENDATIONS_FILE, existing)
        return True
    except Exception as e:
        print(f"Error saving AI recommendations batch: {e}")
        return False


def clear_ai_recommendation(group_hash: str) -> bool:
    """
    Clear a single AI recommendation (call when group content changes).

    Args:
        group_hash: Group hash identifier.

    Returns:
        bool: True if successful.
    """
    recommendations = load_ai_recommendations()

    if group_hash in recommendations:
        del recommendations[group_hash]
        try:
            write_json_file(AI_RECOMMENDATIONS_FILE, recommendations)
            return True
        except Exception as e:
            print(f"Error clearing AI recommendation: {e}")
            return False
    return True  # Successful if entry doesn't exist
