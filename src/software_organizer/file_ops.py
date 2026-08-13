# -*- coding: utf-8 -*-
"""
File Operations Module - Handles software package scanning and file operations.

Contains:
- Software package scanning (multi-category support)
- Version number parsing
- Directory structure retrieval
"""

import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from .config import (
    load_config,
    get_categories,
    get_category_by_extension,
    get_all_formats,
)

_NOISE_WORDS = {
    "app",
    "apple",
    "arm",
    "arm64",
    "build",
    "by",
    "cn",
    "com",
    "crack",
    "dmg",
    "final",
    "fix",
    "for",
    "formac",
    "intel",
    "installer",
    "ked",
    "mac",
    "macos",
    "macked",
    "macwk",
    "mas",
    "osx",
    "patch",
    "pkg",
    "setup",
    "silicon",
    "tnt",
    "u2b",
    "universal",
    "x64",
    "x86",
    "zip",
}

_EDITION_WORDS = {
    "classic",
    "express",
    "lite",
    "plus",
    "premium",
    "pro",
    "professional",
    "standard",
    "studio",
    "ultimate",
    "x",
}

_GENERIC_PRODUCT_NAMES = {
    "autoupdate",
    "download",
    "install",
    "installer",
    "launcher",
    "setup",
    "uninstall",
    "update",
    "updater",
}


def _strip_extension(value: str) -> str:
    """Return filename without its last extension."""
    return os.path.splitext(os.path.basename(value or ""))[0]


def normalize_software_name(value: str, strip_extension: bool = False) -> str:
    """
    Normalize a software name for matching.

    The scanner sees many release naming styles, such as
    "PDF.Expert.v3.11", "PDF Expert 3.11 [TNT]", or "iMazing3forMac".
    This keeps the product words and removes versions, platforms, and release tags.
    """
    raw_value = _strip_extension(value) if strip_extension else os.path.basename(value or "")
    text = unicodedata.normalize("NFKC", raw_value).lower()
    text = text.replace("&", " and ")

    # Handle common suffixes that are often glued to the product name.
    text = re.sub(r"(?:for)?mac(?:os)?$", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[a-z])\d+(?=for$)", " ", text)
    text = re.sub(r"\bfor$", " ", text)
    text = re.sub(r"(?<=[a-z])\d+(?:[._-]\d+)*$", " ", text)

    # Drop bracketed release notes, then normalize separators.
    text = re.sub(r"[\[\(（【{].*?[\]\)）】}]", " ", text)
    text = re.sub(r"[_\-.+]+", " ", text)

    # Remove version/build/year tokens wherever they appear.
    text = re.sub(r"\b(?:v|ver|version)\s*\d+(?:\s+\d+){0,4}[a-z]?\b", " ", text)
    text = re.sub(r"\b(?:build|b)\s*\d+\b", " ", text)
    text = re.sub(r"\b\d+(?:\s+\d+){1,4}[a-z]?\b", " ", text)
    text = re.sub(r"\b20\d{2}\b", " ", text)
    text = re.sub(r"\b\d{1,4}\b\s*$", " ", text)

    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    tokens = [token for token in text.split() if token and token not in _NOISE_WORDS]
    return " ".join(tokens)


def artifact_variant(filename: str) -> str:
    """Keep independently useful package variants out of the same cleanup group."""
    text = unicodedata.normalize("NFKC", _strip_extension(filename)).lower()
    variants = []
    patterns = (
        ("language-pack", r"(?:^|[^a-z0-9])(?:lang(?:uage)?[ _-]?pack|help[ _-]?pack)(?:[^a-z0-9]|$)"),
        ("patch", r"(?:^|[^a-z0-9])(?:patch|crack|keygen|activation)(?:[^a-z0-9]|$)"),
        ("arm64", r"(?:^|[^a-z0-9])(?:arm64|aarch64|apple[ _-]?silicon)(?:[^a-z0-9]|$)"),
        ("intel", r"(?:^|[^a-z0-9])(?:x86[ _-]?64|x64|amd64|intel)(?:[^a-z0-9]|$)"),
        ("universal", r"(?:^|[^a-z0-9])universal(?:[^a-z0-9]|$)"),
    )
    for variant, pattern in patterns:
        if re.search(pattern, text):
            variants.append(variant)
    return "+".join(variants) or "main"


def software_name_similarity(source_name: str, target_name: str) -> float:
    """
    Return a conservative similarity score between two software names.

    1.0 means the normalized names are identical. Scores above ~0.86 are suitable
    for matching files that only differ by punctuation, version, source tag, or
    compact spacing.
    """
    from difflib import SequenceMatcher

    left = normalize_software_name(source_name)
    right = normalize_software_name(target_name)

    if not left or not right:
        return 0.0
    if left == right and left in _GENERIC_PRODUCT_NAMES:
        return 0.0
    if left == right:
        return 1.0
    if left.replace(" ", "") == right.replace(" ", ""):
        return 0.98

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return SequenceMatcher(None, left, right).ratio()

    intersection = left_tokens & right_tokens
    overlap = len(intersection) / max(len(left_tokens), len(right_tokens))
    coverage = len(intersection) / min(len(left_tokens), len(right_tokens))
    string_ratio = SequenceMatcher(None, left, right).ratio()
    token_score = overlap * 0.75 + coverage * 0.25

    # Allow one harmless edition token, e.g. "PDF Expert" vs "PDF Expert Pro".
    extra_tokens = (left_tokens | right_tokens) - intersection
    if (
        coverage == 1.0
        and abs(len(left_tokens) - len(right_tokens)) <= 1
        and extra_tokens <= _EDITION_WORDS
    ):
        return max(0.9, string_ratio)

    # If both sides contain different core product words, do not let a high
    # character ratio merge separate products, e.g. open-codesign vs open-design.
    unmatched_left = left_tokens - right_tokens - _EDITION_WORDS
    unmatched_right = right_tokens - left_tokens - _EDITION_WORDS
    if unmatched_left and unmatched_right:
        return min(string_ratio, token_score)

    return max(string_ratio, token_score)


def _version_sort_key(version: Optional[str]) -> tuple:
    """Convert a version string into a tuple suitable for descending sort."""
    if not version:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))


def _candidate_target_categories(
    source_file: Dict[str, Any], categories: Dict[str, Dict[str, Any]]
) -> set[str]:
    """Return target categories that can reasonably contain the source file."""
    source_ext = source_file.get("extension", "").lower()
    category_id = source_file.get("category")
    category_info = categories.get(category_id, {})

    if category_id and category_info.get("target_dir"):
        return {category_id}

    compatible = {
        cat_id
        for cat_id, cat_info in categories.items()
        if cat_info.get("target_dir")
        and source_ext in {fmt.lower() for fmt in cat_info.get("formats", [])}
    }

    if compatible:
        return compatible
    return {category_id} if category_id else set()


def scan_software(source_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recursively scan the source directory to retrieve all software package files.

    Automatically determines the category based on the file extension.

    Args:
        source_dir: Source directory path. If not specified, read from config.

    Returns:
        List of software package information dictionaries.
    """
    config = load_config()
    source = source_dir or config.get("source_dir", "")

    if not source or not os.path.isdir(source):
        return []

    # Get all configured formats
    all_formats = set(f.lower() for f in get_all_formats())

    software_list = []

    for root, _, files in os.walk(source):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in all_formats:
                file_path = os.path.join(root, filename)
                if os.path.islink(file_path):
                    continue
                rel_path = os.path.relpath(file_path, source)

                # Determine category by extension
                category = get_category_by_extension(ext)

                # Parse software name and version
                name_info = parse_software_name(filename)

                try:
                    stat = os.stat(file_path)
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size = 0
                    mtime = 0

                software_list.append(
                    {
                        "filename": filename,
                        "path": file_path,
                        "rel_path": rel_path,
                        "category": category,  # New field: Category ID
                        "extension": ext,
                        "size": size,
                        "mtime": mtime,
                        "name": name_info["name"],
                        "version": name_info["version"],
                        "build": name_info["build"],
                    }
                )

    # Sort by filename
    software_list.sort(key=lambda x: x["filename"].lower())
    return software_list


def parse_software_name(filename: str) -> Dict[str, Optional[str]]:
    """
    Parse a software filename to extract the name and version number.

    Args:
        filename: The filename to parse.

    Returns:
        Dictionary containing 'name', 'version', and 'build'.
    """
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]

    # Common version number patterns
    version_patterns = [
        r"[._\-\s]v?(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)",  # 1.2.3 or v1.2.3 (dot-separated)
        r"[._\-\s](\d+\.\d+)",  # 1.2
        r"[._\-\s]Build[_\-\s]?(\d+)",  # Build 123
        r"[._\-\s]v(\d+)",  # v2211 (No dots, e.g., Path Finder)
        r"[._\-\s]v?(\d{1,4})(?=\s*(?:[\(\[（【].*)?$)",  # Product 6 or Product 6 (edition)
        r"\((\d+)\)$",  # (123)
    ]

    version = None
    build = None
    name = name_without_ext

    date_pattern = (
        r"(?<!\d)"
        r"((?:19|20)\d{2}[._\-]?(?:0[1-9]|1[0-2])[._\-]?(?:0[1-9]|[12]\d|3[01]))"
        r"(?!\d)"
    )
    date_match = re.search(date_pattern, name_without_ext)
    if date_match:
        raw_date = date_match.group(1)
        digits = re.sub(r"\D", "", raw_date)
        version = f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"
        name = re.sub(date_pattern, " ", name, count=1).strip(" _-")

    for pattern in version_patterns:
        if version:
            break
        match = re.search(pattern, name_without_ext, re.IGNORECASE)
        if match:
            if "build" in pattern.lower():
                build = match.group(1)
            else:
                version = match.group(1)
            # Remove version part from name
            name = re.sub(pattern, "", name, flags=re.IGNORECASE).strip(" _-")
            break

    # Clean up common suffixes in the name
    cleanup_patterns = [
        r"[_\-\s]*(macOS|Mac|OSX|Intel|ARM|Universal|x64|x86).*$",
        r"[_\-\s]*(iOS|iPad|iPhone|Android).*$",
    ]
    for pattern in cleanup_patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE).strip(" _-")

    return {"name": name or name_without_ext, "version": version, "build": build}


def get_target_directories(category_id: str) -> List[Dict[str, Any]]:
    """
    Get the list of subdirectories under the target directory for a given category.

    Args:
        category_id: Category ID.

    Returns:
        List of directory information dictionaries.
    """
    categories = get_categories()

    if category_id not in categories:
        return []

    target_dir = categories[category_id].get("target_dir", "")

    if not target_dir or not os.path.isdir(target_dir):
        return []

    directories = []

    for root, dirs, _ in os.walk(target_dir):
        rel_path = os.path.relpath(root, target_dir)
        if rel_path == ".":
            rel_path = ""
        directories.append(
            {
                "path": root,
                "rel_path": rel_path,
                "name": os.path.basename(root) or target_dir,
            }
        )

    return directories


def scan_target_software(category_id: str = None) -> List[Dict[str, Any]]:
    """
    Scan for existing software in the target directories.

    If no category is specified, scans all categories with configured target directories.

    Args:
        category_id: Optional Category ID. Scans all if None.

    Returns:
        List of software package information dictionaries.
    """
    categories = get_categories()
    software_list = []

    # Determine which categories to scan
    if category_id:
        if category_id not in categories:
            return []
        cats_to_scan = {category_id: categories[category_id]}
    else:
        cats_to_scan = categories

    for cat_id, cat_info in cats_to_scan.items():
        target_dir = cat_info.get("target_dir", "")
        formats = set(f.lower() for f in cat_info.get("formats", []))

        if not target_dir or not os.path.isdir(target_dir):
            continue

        # Do not traverse directory symlinks: managed roots must not expose files
        # from unrelated locations to matching or optional AI analysis.
        for root, _, files in os.walk(target_dir, followlinks=False):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext in formats:
                    file_path = os.path.join(root, filename)
                    if os.path.islink(file_path):
                        continue
                    rel_path = os.path.relpath(file_path, target_dir)
                    parent_dir = os.path.dirname(rel_path)

                    name_info = parse_software_name(filename)

                    try:
                        stat = os.stat(file_path)
                        size = stat.st_size
                        mtime = stat.st_mtime
                    except OSError:
                        size = 0
                        mtime = 0

                    software_list.append(
                        {
                            "filename": filename,
                            "path": file_path,
                            "rel_path": rel_path,
                            "parent_dir": parent_dir,
                            "category": cat_id,
                            "name": name_info["name"],
                            "version": name_info["version"],
                            "build": name_info["build"],
                            "extension": ext,
                            "size": size,
                            "mtime": mtime,
                        }
                    )

    return software_list


def get_unconfigured_categories() -> List[str]:
    """
    Get a list of category IDs that have no target directory configured.

    Returns:
        List of unconfigured category IDs.
    """
    categories = get_categories()
    unconfigured = []

    for cat_id, cat_info in categories.items():
        target_dir = cat_info.get("target_dir", "")
        if not target_dir or not os.path.isdir(target_dir):
            unconfigured.append(cat_id)

    return unconfigured


def format_file_size(size: int) -> str:
    """Format file size into human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ✅ Stable Method - Core matching logic for target files
# Key Design Decisions:
# 1. Supports passing a pre-scanned target_software_list to preserve existing attributes (e.g., location).
# 2. If not provided, scan_target_software will be called to re-scan (external enhancements will be lost).
# Verify call sites in server.py before modification!
def find_target_matches(
    source_file: Dict[str, Any],
    target_software_list: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Find matching items in target directories for a given source file (Strict Type Matching).

    Args:
        source_file: Information dictionary of the source file.
        target_software_list: Optional list of pre-scanned target software. If provided, used instead of re-scanning.

    Returns:
        List of matching target file dictionaries.
    """
    source_name = source_file["name"]
    source_ext = source_file["extension"].lower()
    category_id = source_file["category"]
    source_variant = artifact_variant(source_file.get("filename", source_name))

    categories = get_categories()
    candidate_categories = _candidate_target_categories(source_file, categories)

    # Get all target files for compatible categories. This allows "general" ZIP
    # source files to match Mac/Windows target folders when those categories also
    # accept ZIP archives.
    if target_software_list is not None:
        target_files = []
        for target in target_software_list:
            if not candidate_categories or target.get("category") in candidate_categories:
                target_files.append(target)
    else:
        if len(candidate_categories) == 1:
            target_files = scan_target_software(next(iter(candidate_categories)))
        else:
            target_files = scan_target_software()

    matches = []

    for target in target_files:
        if artifact_variant(target.get("filename", target.get("name", ""))) != source_variant:
            continue
        target_category = target.get("category") or category_id
        target_category_info = categories.get(target_category, {})
        target_formats = {
            fmt.lower() for fmt in target_category_info.get("formats", [])
        }
        cross_format = bool(target_category_info.get("cross_format_match", False))
        target_ext = target.get("extension", "").lower()

        # 1. Extension matching. Cross-format matching is opt-in per category.
        if target_ext != source_ext:
            if not cross_format:
                continue
            if target_formats and (
                source_ext not in target_formats or target_ext not in target_formats
            ):
                continue

        category_target_dir = target_category_info.get("target_dir", "")
        if not category_target_dir and target_category == category_id:
            category_target_dir = categories.get(category_id, {}).get("target_dir", "")

        if not category_target_dir and target_software_list is None:
            continue

        # 2. Case-insensitive and normalized name matching
        score = software_name_similarity(source_name, target.get("name", ""))
        if score >= 0.86:
            # Build absolute path
            parent_dir_rel = target.get("parent_dir", "")
            if category_target_dir:
                if not parent_dir_rel:
                    # Root category directory
                    parent_dir_abs = category_target_dir
                elif os.path.isabs(parent_dir_rel):
                    # Already absolute
                    parent_dir_abs = parent_dir_rel
                else:
                    # Relative path, join it
                    parent_dir_abs = os.path.join(category_target_dir, parent_dir_rel)
            else:
                parent_dir_abs = parent_dir_rel

            # Create enhanced match information
            match_info = dict(target)
            match_info["parent_dir_abs"] = parent_dir_abs
            match_info["match_score"] = round(score, 3)
            match_info["match_reason"] = (
                "exact_name"
                if source_name.lower() == target.get("name", "").lower()
                else "normalized_name"
            )
            matches.append(match_info)

    # Sort matches by version (newest first)
    matches.sort(
        key=lambda x: (x.get("match_score", 0), _version_sort_key(x.get("version"))),
        reverse=True,
    )

    return matches
