# -*- coding: utf-8 -*-
"""
Web Server Module - REST API service based on FastAPI

Provides endpoints for software scanning, analysis, categorization, and transfer.
"""

import os
import sys
import asyncio
import time
import re
import copy
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import business modules
from software_organizer.config import (
    load_config,
    save_config,
    load_ai_config,
    save_ai_config,
)
from software_organizer.file_ops import (
    artifact_variant,
    scan_software,
    scan_target_software,
    get_target_directories,
    format_file_size,
    software_name_similarity,
)
from software_organizer.ai_engines import (
    DEFAULT_DEEPSEEK_MODELS,
    DEFAULT_GEMINI_MODELS,
    suggest_destination,
    group_software_by_name,
    test_deepseek_connection,
    test_gemini_connection,
)
from software_organizer.transfer import batch_move, batch_delete
from software_organizer.database import get_db

# Create FastAPI application
app = FastAPI(title="File Organizer API", version="1.5.1")

def get_static_dir() -> str:
    """Get the static files directory."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "static")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def _version_key(value: Optional[str]) -> tuple:
    """Convert version text into a sortable tuple."""
    if not value:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", str(value)))


def _mask_secret(value: str) -> str:
    """Return a short display-only mask for stored credentials."""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _is_masked_or_empty_secret(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text == "****" or "..." in text


_SENSITIVE_CONFIG_KEYS = {
    "api_key",
    "api_token",
    "client_secret",
    "password",
    "secret",
    "token",
}


def _redact_sensitive_config(value: Any) -> Any:
    """Recursively remove credential-shaped fields from API responses."""
    if isinstance(value, dict):
        return {
            key: _redact_sensitive_config(item)
            for key, item in value.items()
            if key.lower() not in _SENSITIVE_CONFIG_KEYS
        }
    if isinstance(value, list):
        return [_redact_sensitive_config(item) for item in value]
    return value


def _redact_provider_config(config: Dict[str, Any]) -> Dict[str, Any]:
    public_config = dict(config or {})
    api_key = public_config.pop("api_key", "")
    public_config["configured"] = bool(api_key)
    if api_key:
        public_config["api_key_masked"] = _mask_secret(str(api_key))
    return public_config


def _public_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return configuration safe for the frontend and local API clients."""
    public_config = copy.deepcopy(config)

    for provider in ("gemini", "deepseek"):
        public_config[provider] = _redact_provider_config(
            public_config.get(provider, {})
        )

    custom_providers = public_config.get("custom_providers", {})
    if isinstance(custom_providers, dict):
        public_config["custom_providers"] = {
            name: _redact_provider_config(provider_config)
            if isinstance(provider_config, dict)
            else provider_config
            for name, provider_config in custom_providers.items()
        }

    return public_config


def _merge_secret_config(
    existing: Dict[str, Any], incoming: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge model config while preserving stored keys when the UI sends blanks."""
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if key in {"configured", "api_key_masked"}:
            continue
        if key == "api_key" and _is_masked_or_empty_secret(value):
            continue
        merged[key] = value
    return merged


def _target_parent_abs(item: Dict[str, Any], categories: Dict[str, Dict[str, Any]]) -> str:
    """Return the absolute parent directory for a scanned target item."""
    parent_dir = item.get("parent_dir", "")
    category = item.get("category")
    target_dir = categories.get(category, {}).get("target_dir", "")

    if parent_dir and os.path.isabs(parent_dir):
        return parent_dir
    if target_dir:
        return os.path.join(target_dir, parent_dir) if parent_dir else target_dir
    return os.path.dirname(item.get("path", ""))


def _category_for_path(
    path: str, categories: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    """Find the configured category whose target directory contains path."""
    if not path:
        return None

    abs_path = os.path.abspath(path)
    best_match = None
    best_len = -1
    for cat_id, cat_info in categories.items():
        target_dir = cat_info.get("target_dir", "")
        if not target_dir:
            continue
        abs_target = os.path.abspath(target_dir)
        if abs_path == abs_target or abs_path.startswith(abs_target + os.sep):
            if len(abs_target) > best_len:
                best_match = cat_id
                best_len = len(abs_target)
    return best_match


def _is_path_within(path: str, root: str) -> bool:
    """Return whether an absolute path resolves inside an absolute managed root."""
    if not path or not root or not os.path.isabs(path) or not os.path.isabs(root):
        return False
    try:
        resolved_path = os.path.realpath(path)
        resolved_root = os.path.realpath(root)
        return os.path.commonpath([resolved_path, resolved_root]) == resolved_root
    except (OSError, ValueError):
        return False


def _target_roots(config: Dict[str, Any]) -> List[str]:
    return [
        category.get("target_dir", "")
        for category in config.get("categories", {}).values()
        if category.get("target_dir")
    ]


def _source_needs_category_hint(
    source: Dict[str, Any], categories: Dict[str, Dict[str, Any]]
) -> bool:
    """Return True when source category is missing or has no usable target."""
    cat_id = source.get("category")
    return not cat_id or not categories.get(cat_id, {}).get("target_dir")


def _apply_category_from_path(
    source: Dict[str, Any], path: str, categories: Dict[str, Dict[str, Any]]
) -> None:
    """Assign an inferred category when an ambiguous source gets a target path."""
    if not _source_needs_category_hint(source, categories):
        return

    cat_id = _category_for_path(path, categories)
    if cat_id and cat_id in categories:
        source["category"] = cat_id
        source["category_name"] = categories[cat_id]["name"]


def _collect_candidate_directories(
    categories: Dict[str, Dict[str, Any]], max_depth: int = 2
) -> Dict[str, List[str]]:
    """Collect existing target subdirectories, capped to keep AI prompts compact."""
    by_category: Dict[str, List[str]] = {}

    for cat_id, cat_info in categories.items():
        target_dir = cat_info.get("target_dir", "")
        if not target_dir or not os.path.isdir(target_dir):
            by_category[cat_id] = []
            continue

        found = []
        for root, dirs, _ in os.walk(target_dir):
            rel_path = os.path.relpath(root, target_dir)
            if rel_path == ".":
                continue

            depth = len(rel_path.split(os.sep))
            if depth <= max_depth:
                found.append(root)
            if depth >= max_depth:
                dirs[:] = []

        found.sort(key=lambda p: (len(os.path.relpath(p, target_dir).split(os.sep)), p.lower()))
        by_category[cat_id] = found[:120]

    return by_category


def _resolve_suggested_directory(
    suggested: Optional[str],
    candidates: List[str],
    root_dir: str,
) -> Optional[str]:
    """Resolve an AI directory answer to an existing absolute path."""
    if not suggested:
        return None

    raw = str(suggested).strip()
    if not raw:
        return None

    if raw.upper() == "ROOT":
        return root_dir if root_dir and os.path.isdir(root_dir) else None

    expanded = os.path.abspath(os.path.expanduser(raw))
    if os.path.isdir(expanded):
        return expanded

    candidate_paths = []
    if root_dir:
        candidate_paths.append(root_dir)
    candidate_paths.extend(candidates)

    normalized = os.path.normcase(os.path.normpath(raw))
    compact = raw.strip("/").lower()

    for path in candidate_paths:
        if normalized == os.path.normcase(os.path.normpath(path)):
            return path

        labels = {os.path.basename(path).lower()}
        if root_dir:
            try:
                labels.add(os.path.relpath(path, root_dir).lower())
            except ValueError:
                pass

        tail = "/".join(path.split(os.sep)[-2:]).lower()
        labels.add(tail)
        if compact in labels:
            return path

    return None


def _resolve_ai_refs(refs: List[str], items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve AI-returned filename/name references back to scanned file objects."""
    resolved = []
    used_paths = set()

    for ref in refs or []:
        if not ref:
            continue
        ref_text = str(ref)

        exact = next(
            (
                item
                for item in items
                if item.get("filename") == ref_text or item.get("name") == ref_text
            ),
            None,
        )

        if exact is None:
            scored = []
            for item in items:
                score = max(
                    software_name_similarity(ref_text, item.get("filename", "")),
                    software_name_similarity(ref_text, item.get("name", "")),
                )
                if score >= 0.9:
                    scored.append((score, item))
            if scored:
                exact = max(scored, key=lambda pair: pair[0])[1]

        if exact and exact.get("path") not in used_paths:
            resolved.append(exact)
            used_paths.add(exact.get("path"))

    return resolved


def _apply_keep_recommendations(groups: List[Dict[str, Any]]) -> None:
    """Mark which files should be checked by default in入库 mode."""
    for group in groups:
        files = group.get("files", [])
        if not files:
            continue

        for item in files:
            item["recommended_keep"] = False
            item["recommend_reason"] = ""

        source_files = [item for item in files if item.get("location") == "source"]
        target_files = [item for item in files if item.get("location") == "target"]

        if not target_files:
            for item in source_files:
                item["recommended_keep"] = True
                item["recommend_reason"] = "new_source"
            continue

        ranked = []
        for item in files:
            ranked.append(
                (
                    bool(item.get("version")),
                    _version_key(item.get("version")),
                    item.get("mtime", 0) or 0,
                    1 if item.get("location") == "source" else 0,
                    item,
                )
            )

        best = max(ranked, key=lambda row: row[:4])
        best_key = best[:3]
        for has_version, version, mtime, _is_source, item in ranked:
            keep = (has_version, version, mtime) == best_key
            item["recommended_keep"] = keep
            if keep:
                item["recommend_reason"] = (
                    "latest_source"
                    if item.get("location") == "source"
                    else "target_is_newer_or_same"
                )


# Mount static files
app.mount("/static", StaticFiles(directory=get_static_dir()), name="static")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


# ==============================================================================
# Request Models
# ==============================================================================


class ConfigUpdate(BaseModel):
    """Configuration update request."""

    source_dir: Optional[str] = None
    categories: Optional[Dict[str, Dict[str, Any]]] = None
    gemini: Optional[Dict] = None
    deepseek: Optional[Dict] = None
    ollama: Optional[Dict] = None
    custom_providers: Optional[Dict] = None
    current_engine: Optional[str] = None
    use_ai: Optional[bool] = None


class CategoryUpdate(BaseModel):
    """Category update request."""

    cat_id: str
    name: Optional[str] = None
    formats: Optional[List[str]] = None
    target_dir: Optional[str] = None
    cross_format_match: Optional[bool] = None


class CategoryCreate(BaseModel):
    """Category creation request."""

    cat_id: str
    name: str
    formats: List[str]


class AnalyzeRequest(BaseModel):
    """Analysis request."""

    engine: str = "gemini"
    use_ai: bool = False


class TransferRequest(BaseModel):
    """Transfer request."""

    files: List[str]
    destination: str
    overwrite: bool = False


class DeleteRequest(BaseModel):
    """Deletion request."""

    files: List[str]


class BrowseRequest(BaseModel):
    """Directory browsing request."""

    path: Optional[str] = None


class ModelRequest(BaseModel):
    """AI model request."""

    api_key: Optional[str] = None
    url: Optional[str] = None


# ==============================================================================
# Routes: Index
# ==============================================================================


@app.get("/")
async def read_index():
    """Return the index page."""
    return FileResponse(os.path.join(get_static_dir(), "index.html"))


@app.get("/api/health")
async def health_check():
    """Return a stable marker used to identify the local backend."""
    return {"app": "file-organizer", "status": "ok"}


# ==============================================================================
# Routes: Configuration Management
# ==============================================================================


@app.get("/api/config")
async def get_config():
    """Get the current configuration."""
    return _public_config(load_config())


@app.post("/api/config")
async def update_config(config_update: ConfigUpdate):
    """Update the configuration."""
    config = load_config()

    update_data = config_update.model_dump(exclude_none=True)
    for key, value in update_data.items():
        if key in ("gemini", "deepseek") and isinstance(value, dict):
            config[key] = _merge_secret_config(config.get(key, {}), value)
        elif key == "custom_providers" and isinstance(value, dict):
            providers = dict(config.get("custom_providers", {}))
            for provider_name, provider_config in value.items():
                if isinstance(provider_config, dict):
                    providers[provider_name] = _merge_secret_config(
                        providers.get(provider_name, {}), provider_config
                    )
                else:
                    providers[provider_name] = provider_config
            config[key] = providers
        elif isinstance(value, dict) and key in config and isinstance(config[key], dict):
            config[key].update(value)
        else:
            config[key] = value

    save_config(config)
    if any(
        key in update_data
        for key in ("gemini", "deepseek", "ollama", "custom_providers", "current_engine")
    ):
        _ai_status_cache["data"] = None
        _ai_status_cache["time"] = 0
    return {"status": "success", "config": _public_config(config)}


@app.get("/api/ai-config")
async def get_ai_config():
    """Get the AI configuration."""
    return _redact_sensitive_config(load_ai_config())


@app.post("/api/ai-config")
async def update_ai_config(ai_config: Dict[str, Any]):
    """Update the AI configuration."""
    save_ai_config(ai_config)
    return {"status": "success"}


# ==============================================================================
# Routes: Category Management
# ==============================================================================


@app.get("/api/categories")
async def get_all_categories():
    """Get all software categories."""
    from software_organizer.config import get_categories

    return get_categories()


@app.post("/api/categories")
async def create_category(request: CategoryCreate):
    """Create a new category."""
    from software_organizer.config import add_category

    result = add_category(request.cat_id, request.name, request.formats)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success"}


@app.put("/api/categories/{cat_id}")
async def update_category_endpoint(cat_id: str, request: CategoryUpdate):
    """Update a category."""
    from software_organizer.config import update_category

    result = update_category(
        cat_id,
        name=request.name,
        formats=request.formats,
        target_dir=request.target_dir,
        cross_format_match=request.cross_format_match,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success"}


@app.delete("/api/categories/{cat_id}")
async def delete_category_endpoint(cat_id: str):
    """Delete a category."""
    from software_organizer.config import delete_category

    result = delete_category(cat_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success"}


@app.post("/api/categories/{cat_id}/restore")
async def restore_category_endpoint(cat_id: str):
    """Restore category defaults."""
    from software_organizer.config import restore_category_defaults

    result = restore_category_defaults(cat_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success"}


# ==============================================================================
# Routes: Directory Browsing
# ==============================================================================


@app.post("/api/browse")
def browse_directory(request: BrowseRequest):
    """Browse a directory."""
    path = request.path or os.path.expanduser("~")

    if not os.path.isdir(path):
        raise HTTPException(
            status_code=400, detail="Path does not exist or is not a directory"
        )

    items = []
    try:
        for name in sorted(os.listdir(path)):
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path) and not name.startswith("."):
                items.append({"name": name, "path": full_path, "is_dir": True})
    except PermissionError:
        raise HTTPException(
            status_code=403, detail="Permission denied to access this directory"
        )

    return {"current": path, "parent": os.path.dirname(path), "items": items}


# ==============================================================================
# Routes: Software Scanning
# ==============================================================================


@app.get("/api/software")
def get_software_list():
    """Get the software list from the source directory."""
    from software_organizer.config import get_categories

    software_list = scan_software()
    categories = get_categories()

    # Add formatted file size and category name
    for item in software_list:
        item["size_formatted"] = format_file_size(item["size"])
        cat_id = item.get("category")
        if cat_id and cat_id in categories:
            item["category_name"] = categories[cat_id]["name"]
        else:
            item["category_name"] = "Unknown"

    # Statistics by category
    category_counts = {}
    for cat_id, cat_info in categories.items():
        count = len([s for s in software_list if s.get("category") == cat_id])
        category_counts[cat_id] = {"name": cat_info["name"], "count": count}

    return {
        "total": len(software_list),
        "category_counts": category_counts,
        "software": software_list,
        "categories": categories,
    }


@app.get("/api/software/target")
def get_all_target_software():
    """Get all software from target directories."""
    from software_organizer.config import get_categories

    software_list = scan_target_software()
    categories = get_categories()

    # Add category names
    for item in software_list:
        cat_id = item.get("category")
        if cat_id and cat_id in categories:
            item["category_name"] = categories[cat_id]["name"]

    return {"count": len(software_list), "software": software_list}


@app.get("/api/software/target/{category_id}")
def get_target_software_by_category(category_id: str):
    """Get software list for a specific category in target directories."""
    from software_organizer.config import get_categories

    categories = get_categories()
    if category_id not in categories:
        raise HTTPException(status_code=400, detail=f"分类 '{category_id}' 不存在")

    software_list = scan_target_software(category_id)
    return {
        "category": category_id,
        "category_name": categories[category_id]["name"],
        "count": len(software_list),
        "software": software_list,
    }


@app.get("/api/directories/{category_id}")
def get_directories(category_id: str):
    """Get target directory structure for a specific category."""
    from software_organizer.config import get_categories

    categories = get_categories()
    if category_id not in categories:
        raise HTTPException(status_code=400, detail=f"分类 '{category_id}' 不存在")

    directories = get_target_directories(category_id)
    return {"category": category_id, "directories": directories}


# ==============================================================================
# Routes: AI Analysis
# ==============================================================================

# ==============================================================================
# Routes: History and Rules
# ==============================================================================


class KeepRule(BaseModel):
    """Keep rule request."""

    filename: Optional[str] = None  # Filename (primary identifier)
    file_path: Optional[str] = None  # File path (secondary identifier)
    keep: bool
    software_name: Optional[str] = None  # Software name (compatibility)


class RetentionPolicyRequest(BaseModel):
    """Structured retention policy request."""

    software_name: str
    keep_latest: Optional[int] = None
    never_delete: Optional[bool] = None
    reset: bool = False


@app.get("/api/history")
async def get_history(limit: int = 100, action: Optional[str] = None):
    """Get operation history."""
    db = get_db()
    logs = db.get_transfer_logs(limit=limit, action=action)
    return {"logs": logs}


@app.post("/api/rules/keep")
async def update_keep_rule(rule: KeepRule):
    """Update keep rule."""
    from software_organizer.persistence import save_keep_rule

    # Use file path as the primary identifier for precise duplicate and version management.
    # This prevents "same name, different path" duplicates from being incorrectly matched.
    identifier = rule.file_path or rule.filename or rule.software_name

    if not identifier:
        return {"status": "error", "message": "Missing identifier"}

    success = save_keep_rule(identifier, rule.keep, rule.software_name)
    return {"status": "success" if success else "error"}


@app.get("/api/retention-rules")
async def get_retention_rules_endpoint():
    """Get structured retention policies."""
    from software_organizer.persistence import load_retention_rules

    return load_retention_rules()


@app.put("/api/retention-rules")
async def update_retention_rules_endpoint(request: Dict[str, Any]):
    """Update global structured retention policies."""
    from software_organizer.persistence import load_retention_rules, save_retention_rules

    rules = load_retention_rules()
    if "global_keep_latest" in request:
        try:
            rules["global_keep_latest"] = max(0, int(request["global_keep_latest"]))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="global_keep_latest 必须是数字")

    for key in ("protected_directories", "protected_keywords"):
        if key in request:
            value = request[key]
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail=f"{key} 必须是数组")
            rules[key] = [str(item) for item in value if str(item).strip()]

    success = save_retention_rules(rules)
    return {"status": "success" if success else "error", "rules": rules}


@app.post("/api/retention/software")
async def update_software_retention_policy(request: RetentionPolicyRequest):
    """Create or update a software-level retention policy."""
    from software_organizer.persistence import save_software_retention_policy

    result = save_software_retention_policy(
        software_name=request.software_name,
        keep_latest=request.keep_latest,
        never_delete=request.never_delete,
        reset=request.reset,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "保存失败"))
    return result


# ==============================================================================
# 路由：AI 分析与软件匹配
# ==============================================================================


@app.post("/api/analyze")
def analyze_software(request: AnalyzeRequest):
    """
    AI 分析文件分组关联关系，并包含智能匹配建议。
    """
    from software_organizer.config import get_categories
    from software_organizer.file_ops import (
        get_unconfigured_categories,
        find_target_matches,
    )
    from software_organizer.persistence import is_kept

    config = load_config()
    categories = get_categories()

    # 检查未配置目录的分类
    _unconfigured = get_unconfigured_categories()

    # 获取源软件列表
    source_software = scan_software()

    # 获取目标软件列表
    target_software = scan_target_software()

    # 优先为目标软件添加分类名称和 Keep 状态（确保后续匹配时对象已增强）
    for t in target_software:
        t["location"] = "target"
        cat_id = t.get("category")
        if cat_id and cat_id in categories:
            t["category_name"] = categories[cat_id]["name"]

        # 检查该文件是否被标记为保留
        # 优先使用 path (新版规则), 其次使用 name/filename (兼容旧版)
        t["is_kept"] = (
            is_kept(t["path"])
            or is_kept(t.get("filename", ""))
            or is_kept(t.get("name", ""))
        )

    # 为源软件添加增强信息：匹配项、推荐路径、Keep状态
    for s in source_software:
        s["location"] = "source"
        s["size_formatted"] = format_file_size(s.get("size", 0))
        cat_id = s.get("category")
        if cat_id and cat_id in categories:
            s["category_name"] = categories[cat_id]["name"]

        # 1. 查找匹配项 (严格类型)
        matches = find_target_matches(s, target_software)
        if matches:
            _apply_category_from_path(
                s, matches[0].get("parent_dir_abs") or matches[0].get("path", ""), categories
            )
            cat_id = s.get("category")

        # [Defensive Programming] 强制确保 matches 中的文件具有 location 属性
        for m in matches:
            if "location" not in m:
                m["location"] = "target"

        s["matches"] = matches

        # 2. 检查 Keep 状态
        # 优先使用 path (新版规则), 其次使用 name (兼容旧版)
        s["is_kept"] = is_kept(s["path"]) or is_kept(s.get("name", ""))

        # 3. 确定推荐路径
        # 逻辑：
        # - 如果有匹配项：
        #   - 默认推荐第一个匹配项的父目录 (matches 已按版本排序，最新的在前)
        #   - 直接使用 parent_dir_abs（绝对路径）
        # - 如果无匹配项：
        #   - 使用分类默认目录
        recommended_path = ""
        if matches:
            # 直接使用 find_target_matches 返回的绝对路径
            recommended_path = matches[0].get("parent_dir_abs", "")

        if not recommended_path and cat_id and cat_id in categories:
            recommended_path = categories[cat_id].get("target_dir", "")

        s["recommended_path"] = recommended_path

    # ... (后续分组逻辑，这里为了保持代码完整性，需要小心替换)
    # 由于 analyze_software 函数较长，我们只替换主要逻辑部分
    # 这里为了简单，我们假设分组逻辑保持不变，但利用 s['matches']

    # 重新构建分组结构，基于我们的精确匹配
    # 如果使用了精确匹配，AI 分析可能不再是主要的，或者作为辅助
    # 但为了向后兼容和利用 AI 能力，我们保留原来的 AI 流程，
    # 并在返回结果中确保 source_software 携带了 matches 信息。

    # 简化：直接返回分组结果，利用前端处理显示

    all_software = source_software + target_software

    # ... (调用 AI 或 fallback)
    try:
        # 优化：先用规则匹配，只将未匹配的文件发送给 AI
        rule_matched_groups = []  # 规则已匹配的分组
        needs_ai_sources = []  # 需要 AI 处理的源文件

        for s in source_software:
            matches = s.get("matches", [])
            if matches:
                # 规则匹配成功，直接构建分组
                group_files = [s] + matches
                group_files.sort(
                    key=lambda x: (
                        1 if x.get("location") == "source" else 0,
                        _version_key(x.get("version")),
                        x.get("mtime", 0) or 0,
                    ),
                    reverse=True,
                )

                software_name = s.get("name", s["filename"])
                ext = s.get("extension", "")
                if ext:
                    software_name = f"{software_name} ({ext})"

                rule_matched_groups.append(
                    {
                        "software_name": software_name,
                        "files": group_files,
                        "suggested_path": s.get("recommended_path", ""),
                        "source_files": [s["filename"]],
                        "target_files": [m["filename"] for m in matches],
                        "source_path": s["path"],
                        "match_source": "rule",  # 标记来源
                    }
                )
            else:
                # 无匹配，可能需要 AI 处理
                needs_ai_sources.append(s)

        ai_groups = []

        # 根据 use_ai 决定是否使用 AI 分析
        if request.use_ai and needs_ai_sources:
            try:
                from software_organizer.ai_engines import (
                    analyze_software_relation,
                )

                print(
                    f"[AI 优化] 规则已匹配 {len(source_software) - len(needs_ai_sources)} 个，"
                    f"发送 {len(needs_ai_sources)} 个未匹配文件给 AI"
                )

                result = analyze_software_relation(
                    engine_choice=request.engine,
                    config=config,
                    source_software=needs_ai_sources,  # 只发送未匹配的
                    target_software=target_software,
                )
                raw_ai_groups = result.get("groups", [])
                matched_source_paths = set()
                ai_groups = []

                for group in raw_ai_groups:
                    source_refs = group.get("source_files") or [
                        group.get("software_name", "")
                    ]
                    target_refs = group.get("target_files") or []
                    source_objs = _resolve_ai_refs(source_refs, needs_ai_sources)
                    target_objs = _resolve_ai_refs(target_refs, target_software)
                    source_variants = {
                        artifact_variant(item.get("filename", "")) for item in source_objs
                    }
                    target_objs = [
                        item
                        for item in target_objs
                        if artifact_variant(item.get("filename", "")) in source_variants
                    ]

                    # A group without target files still needs path suggestion below.
                    if not source_objs or not target_objs:
                        continue

                    target_objs.sort(
                        key=lambda item: _version_key(item.get("version")), reverse=True
                    )
                    suggested_path = _target_parent_abs(target_objs[0], categories)
                    for source in source_objs:
                        _apply_category_from_path(source, suggested_path, categories)
                        source["recommended_path"] = suggested_path
                        matched_source_paths.add(source["path"])

                    ai_groups.append(
                        {
                            "software_name": group.get("software_name")
                            or source_objs[0].get("name", source_objs[0]["filename"]),
                            "files": source_objs + target_objs,
                            "suggested_path": suggested_path,
                            "source_files": [item["filename"] for item in source_objs],
                            "target_files": [item["filename"] for item in target_objs],
                            "source_path": source_objs[0]["path"],
                            "match_source": "ai_relation",
                        }
                    )

                # Anything not confidently matched to a target still gets path advice.
                remaining_unmatched = [
                    s for s in needs_ai_sources if s["path"] not in matched_source_paths
                ]

            except Exception as e:
                print(f"AI Analysis failed: {e}")
                import traceback

                traceback.print_exc()
                ai_groups = []
                remaining_unmatched = needs_ai_sources

        else:
            # Non-AI Mode: All rule-unmatched files are treated as "remaining unmatched"
            # We will try to apply smart suggestions to them
            remaining_unmatched = needs_ai_sources
            ai_groups = []

        # --- Smart Path Suggestion for Remaining Unmatched Files ---
        if remaining_unmatched:
            from software_organizer.ai_engines import (
                suggest_best_directory,
                suggest_directory_by_category,
                batch_analyze_path_suggestions,
            )

            candidate_dirs_by_category = _collect_candidate_directories(categories)
            all_candidate_dirs = sorted(
                {
                    path
                    for dirs in candidate_dirs_by_category.values()
                    for path in dirs
                },
                key=len,
                reverse=True,
            )

            # AI Enhanced Analysis
            ai_suggestions = {}
            if request.use_ai:
                try:
                    print(
                        f"[AI 增强] 正在为 {len(remaining_unmatched)} 个新增文件请求 AI 路径建议..."
                    )
                    sources_by_category = {}
                    for item in remaining_unmatched:
                        cat_id = item.get("category")
                        if _source_needs_category_hint(item, categories):
                            cat_id = "__all__"
                        sources_by_category.setdefault(cat_id, []).append(item)

                    for cat_id, items in sources_by_category.items():
                        available_dirs = (
                            all_candidate_dirs
                            if cat_id == "__all__"
                            else candidate_dirs_by_category.get(cat_id, [])
                        )
                        if not available_dirs:
                            continue

                        ai_result = batch_analyze_path_suggestions(
                            engine_choice=request.engine,
                            config=config,
                            software_list=items,
                            available_directories=available_dirs,
                        )

                        # Convert list result to dict for easy lookup
                        for sug in ai_result.get("suggestions", []):
                            ai_suggestions[sug["filename"]] = sug
                except Exception as e:
                    print(f"AI Batch path suggestion failed: {e}")

            for s in remaining_unmatched:
                software_name = s.get("name", s["filename"])
                filename = s["filename"]
                cat_id = s.get("category")
                category_root = categories.get(cat_id, {}).get("target_dir", "")
                candidate_dirs = candidate_dirs_by_category.get(cat_id, [])

                if _source_needs_category_hint(s, categories):
                    category_root = ""
                    candidate_dirs = all_candidate_dirs

                best_dir = None
                match_source = "default"
                path_source = "default"

                # 1. Use AI Suggestion if available
                if filename in ai_suggestions:
                    sug = ai_suggestions[filename]
                    best_dir = _resolve_suggested_directory(
                        sug.get("suggested_path"),
                        candidate_dirs,
                        category_root,
                    )
                    if best_dir:
                        match_source = "ai_enhanced"
                        path_source = "ai_vision"
                        print(
                            f"  [AI 推荐] {filename} -> {os.path.basename(best_dir)} ({sug.get('reason', '')})"
                        )

                # 2. Fallback to Local Smart Rules
                if not best_dir:
                    # Try Brand/Keyword Match
                    best_dir = suggest_best_directory(
                        software_name, target_software, candidate_dirs
                    )

                    if best_dir:
                        match_source = "smart_rule"
                        path_source = "smart_brand"
                    else:
                        # Try Category Keyword Match
                        best_dir = suggest_directory_by_category(
                            software_name, candidate_dirs
                        )
                        if best_dir:
                            match_source = "smart_rule"
                            path_source = "smart_category"

                if best_dir:
                    _apply_category_from_path(s, best_dir, categories)
                    s["recommended_path"] = best_dir

                # Create a group for this file
                ai_groups.append(
                    {
                        "software_name": software_name,
                        "files": [s],
                        "suggested_path": best_dir or s.get("recommended_path", ""),
                        "source_files": [s["filename"]],
                        "target_files": [],
                        "source_path": s["path"],
                        "match_source": match_source,
                        "path_source": path_source,
                    }
                )

        # 合并规则匹配结果和 AI 结果
        ai_groups = rule_matched_groups + ai_groups

        # --- Common Group Building Logic ---
        groups = []
        processed_files = set()

        # 1. Process explicit groups (from AI or Rule Matching)
        for group_data in ai_groups:
            # We reconstruct the group to ensure clean object references and deduplication
            current_group_files = []
            suggested_path = group_data.get("suggested_path", "")
            group_name = group_data.get("software_name", "Unknown")

            # Add Source Files
            source_filenames = set(group_data.get("source_files", []))
            # Also support direct file objects if we populated them in Rule mode
            direct_files = group_data.get("files", [])

            if direct_files:
                for f in direct_files:
                    if f["path"] not in processed_files:
                        current_group_files.append(f)
                        processed_files.add(f["path"])
            else:
                # AI Mode: Match by filename
                for s in source_software:
                    # 修改：允许同一个 source file 进入多个组 (针对 Universal 情况)
                    # 只要 filename 匹配，就加入。
                    # processed_files 仅用于最后的 "未分组文件" 检查
                    if s["filename"] in source_filenames:
                        current_group_files.append(s)
                        processed_files.add(s["path"])

                # Add Target Files
                target_filenames = set(group_data.get("target_files", []))
                for t in target_software:
                    if (
                        t["filename"] in target_filenames
                        and t["path"] not in processed_files
                    ):
                        current_group_files.append(t)
                        processed_files.add(t["path"])

            if current_group_files:
                # Sort: Source first, then Version Descending
                current_group_files.sort(
                    key=lambda x: (
                        1 if x.get("location") == "source" else 0,
                        _version_key(x.get("version")),
                        x.get("mtime", 0) or 0,
                    ),
                    reverse=True,
                )

                groups.append(
                    {
                        "software_name": group_name,
                        "files": current_group_files,
                        "suggested_path": suggested_path,
                    }
                )

        # 2. Add remaining un-grouped Source files
        for s in source_software:
            if s["path"] not in processed_files:
                groups.append(
                    {
                        "software_name": s.get("name", s["filename"]),
                        "files": [s],
                        "suggested_path": s.get("recommended_path", ""),
                    }
                )
                processed_files.add(s["path"])

        _apply_keep_recommendations(groups)

        return {
            "groups": groups,
            "source_software": source_software,
            "target_software": target_software,
            "categories": categories,
            "unconfigured_categories": _unconfigured,
        }

    except Exception as e:
        print(f"Critical Error in Analyze: {e}")
        # Final Fallback to pure name grouping
        groups = group_software_by_name(all_software)
        result_groups = []
        for name, items in groups.items():
            # 排序：源文件优先，然后按版本号降序
            items.sort(
                key=lambda x: (
                    1 if x.get("location") == "source" else 0,
                    _version_key(x.get("version")),
                    x.get("mtime", 0) or 0,
                ),
                reverse=True,
            )
            # 查找该组中的源文件
            src_item = next((i for i in items if i.get("location") == "source"), None)

            # 只显示包含源文件的组
            if src_item:
                suggested = src_item.get("recommended_path", "")

                result_groups.append(
                    {"software_name": name, "files": items, "suggested_path": suggested}
                )

        _apply_keep_recommendations(result_groups)

        return {
            "groups": result_groups,
            "source_software": source_software,
            "target_software": target_software,
            "categories": categories,
            "unconfigured_categories": [],
            "fallback": True,
        }


@app.post("/api/analyze/duplicates")
def analyze_duplicates():
    """
    分析目标目录中的重复文件（按分类独立分析）。

    Returns:
        分组结果
    """
    from software_organizer.config import get_categories
    from software_organizer.ai_engines import group_software_by_name
    from software_organizer.persistence import (
        annotate_duplicate_retention,
        is_kept,
        has_keep_rule,
    )

    categories = get_categories()
    duplicate_groups = []

    # 遍历每个分类独立处理，满足"分开操作"的需求
    for cat_id, cat_info in categories.items():
        # 扫描该分类下的文件
        cat_software = scan_target_software(category_id=cat_id)

        if not cat_software:
            continue

        # 分组
        cross_format = cat_info.get("cross_format_match", False)
        groups = group_software_by_name(cat_software, cross_format_match=cross_format)

        # 筛选重复项 (数量 > 1)
        for name_key, items in groups.items():
            if len(items) > 1:
                items.sort(
                    key=lambda item: (
                        bool(item.get("version")),
                        _version_key(item.get("version")),
                        item.get("mtime", 0) or 0,
                        item.get("size", 0) or 0,
                    ),
                    reverse=True,
                )

                base_name = items[0]["name"]
                ext = items[0]["extension"]
                retention_summary = annotate_duplicate_retention(items, base_name)

                # 标记位置为 target (虽然 scan_target_software 也可以推断)
                for item in items:
                    item["location"] = "target"
                    item["category_name"] = cat_info["name"]
                    # 补充格式化大小
                    item["size_formatted"] = format_file_size(item.get("size", 0))

                    # 手动 Keep 规则优先，其次结构化保留策略。
                    # 硬保护策略（永不清理/目录排除/关键词排除）不能被默认清理覆盖。
                    manual_keep = None
                    if has_keep_rule(item["path"]):
                        item["has_keep_rule"] = True
                        manual_keep = is_kept(item["path"])
                    elif has_keep_rule(item["filename"]):
                        item["has_keep_rule"] = True
                        manual_keep = is_kept(item["filename"])
                    else:
                        item["has_keep_rule"] = False
                    item["manual_keep"] = manual_keep

                    if item.get("retention_protected"):
                        item["is_kept"] = True
                    elif manual_keep is not None:
                        item["is_kept"] = bool(manual_keep)
                        item["recommended_keep"] = bool(manual_keep)
                        item["recommend_reason"] = (
                            "手动保留" if manual_keep else "手动取消保留"
                        )
                    else:
                        item["is_kept"] = False

                protected_count = sum(
                    1 for item in items if item.get("retention_protected")
                )
                recommended_count = sum(
                    1
                    for item in items
                    if item.get("is_kept") or item.get("recommended_keep")
                )
                retention_summary.update(
                    {
                        "protected_count": protected_count,
                        "recommended_count": recommended_count,
                        "delete_candidate_count": max(
                            0, len(items) - recommended_count
                        ),
                    }
                )

                variant = artifact_variant(items[0].get("filename", ""))
                variant_labels = {
                    "language-pack": "语言包",
                    "patch": "补丁/激活",
                    "arm64": "ARM64",
                    "intel": "Intel",
                    "universal": "Universal",
                }
                variant_text = " · ".join(
                    variant_labels.get(part, part) for part in variant.split("+")
                    if part != "main"
                )
                variant_suffix = f" · {variant_text}" if variant_text else ""
                group_name = f"{base_name}{variant_suffix} ({ext}) - {cat_info['name']}"

                duplicate_groups.append(
                    {
                        "software_name": group_name,
                        "files": items,
                        "suggested_path": "",  # 自我去重无需建议路径
                        "is_duplicate_group": True,  # 标记为查重组
                        "retention_summary": retention_summary,
                    }
                )

    return {"groups": duplicate_groups, "count": len(duplicate_groups)}


# ==============================================================================
# AI 建议持久化 API
# ==============================================================================


@app.get("/api/ai-recommendations")
async def get_ai_recommendations():
    """获取已缓存的 AI 建议"""
    from software_organizer.persistence import load_ai_recommendations

    recommendations = load_ai_recommendations()
    return {"recommendations": recommendations}


@app.post("/api/ai-recommendations")
async def save_ai_recommendations(request: Dict[str, Any]):
    """批量保存 AI 建议"""
    from software_organizer.persistence import save_ai_recommendations_batch

    recommendations = request.get("recommendations", {})
    success = save_ai_recommendations_batch(recommendations)
    return {"status": "success" if success else "error"}


@app.post("/api/analyze/duplicates/ai")
def analyze_duplicates_ai(request: Dict[str, Any]):
    """
    使用 AI 分析重复文件组（增强模式）。
    支持批次处理，超过 50 组自动分批。
    仅返回分析建议，不修改数据。
    """
    from software_organizer.ai_engines import analyze_duplicate_groups

    groups = request.get("groups", [])
    config = load_config()

    # 获取当前选中的 AI 引擎 (关键：使用 current_engine 而不是 ai_provider)
    engine_choice = config.get("current_engine", "gemini")

    if not groups:
        return {"recommendations": []}

    # 批次处理：每次处理 50 组
    BATCH_SIZE = 50
    all_recommendations = []

    for i in range(0, len(groups), BATCH_SIZE):
        batch = groups[i : i + BATCH_SIZE]
        result = analyze_duplicate_groups(engine_choice, config, batch)

        if result and "recommendations" in result:
            # 调整索引，加上批次偏移量
            for rec in result["recommendations"]:
                rec["group_index"] = rec["group_index"] + i
            all_recommendations.extend(result["recommendations"])

    return {"recommendations": all_recommendations}


@app.post("/api/analyze/local")
def analyze_local():
    """本地分析（不调用 AI）- 按名称分组"""
    source_software = scan_software()
    groups = group_software_by_name(source_software)

    result = []
    for name, items in groups.items():
        result.append(
            {
                "software_name": name,
                "files": items,
                "count": len(items),
                "latest": items[0] if items else None,
            }
        )

    return {"groups": result, "total_groups": len(result)}


@app.post("/api/suggest-path")
def get_path_suggestion(
    software_name: str, platform: str, engine: str = "gemini"
):
    """获取路径建议"""
    config = load_config()
    directories = get_target_directories(platform)
    existing_paths = [d["rel_path"] for d in directories if d["rel_path"]]

    result = suggest_destination(
        engine_choice=engine,
        config=config,
        software_name=software_name,
        platform=platform,
        existing_paths=existing_paths,
    )

    return result


# ==============================================================================
# 路由：转移和删除
# ==============================================================================


@app.post("/api/transfer")
def transfer_software(request: TransferRequest):
    """转移文件"""
    if not request.files:
        raise HTTPException(status_code=400, detail="没有选择文件")

    if not request.destination:
        raise HTTPException(status_code=400, detail="没有指定目标目录")

    config = load_config()
    source_root = config.get("source_dir", "")
    if not source_root or any(
        not _is_path_within(file_path, source_root) for file_path in request.files
    ):
        raise HTTPException(status_code=400, detail="只能转移已配置源目录中的文件")

    if not any(_is_path_within(request.destination, root) for root in _target_roots(config)):
        raise HTTPException(status_code=400, detail="目标目录不在已配置的分类目录中")

    result = batch_move(request.files, request.destination, request.overwrite)

    # 记录到数据库
    db = get_db()
    for item in result["success"]:
        db.log_transfer(
            filename=os.path.basename(item["source"]),
            action="transfer",
            source_path=item["source"],
            destination_path=item["destination"],
        )

    return result


@app.post("/api/delete")
def delete_software_files(request: DeleteRequest):
    """删除文件"""
    if not request.files:
        raise HTTPException(status_code=400, detail="没有选择文件")

    roots = _target_roots(load_config())
    if not roots or any(
        not any(_is_path_within(file_path, root) for root in roots)
        for file_path in request.files
    ):
        raise HTTPException(status_code=400, detail="只能清理已配置目标目录中的文件")

    result = batch_delete(request.files)

    # 记录到数据库
    db = get_db()
    for item in result["success"]:
        db.log_transfer(
            filename=os.path.basename(item["deleted"]),
            action="delete",
            source_path=item["deleted"],
        )

    return result


# ==============================================================================
# 路由：AI 模型测试
# ==============================================================================


@app.post("/api/models/{provider}")
async def list_models(provider: str, request: ModelRequest):
    """获取可用模型列表"""
    # Fast preset list. Connection testing can refresh Gemini models from the API.
    models = {
        "gemini": DEFAULT_GEMINI_MODELS,
        "deepseek": DEFAULT_DEEPSEEK_MODELS,
        "ollama": [],  # 需要从 Ollama 服务获取
    }

    return {"models": models.get(provider, [])}


@app.post("/api/test-connection")
async def test_connection(request: Dict[str, Any]):
    """
    测试 AI 连接并获取可用模型列表。

    Returns:
        {
            "status": "ok",
            "message": str,
            "models": List[str]  # 可用模型列表
        }
    """
    provider = request.get("provider", "")
    api_key = request.get("api_key", "")
    url = request.get("url", "")
    model_name = request.get("model_name", "")
    saved_config = load_config()

    try:
        if provider == "gemini":
            if not api_key:
                api_key = saved_config.get("gemini", {}).get("api_key", "")
            if not api_key:
                raise HTTPException(status_code=400, detail="请输入 API Key")

            models = await asyncio.to_thread(
                test_gemini_connection, api_key, model_name
            )
            return {
                "status": "ok",
                "message": "连接成功",
                "models": models,
            }

        elif provider == "deepseek":
            if not api_key:
                api_key = saved_config.get("deepseek", {}).get("api_key", "")
            if not api_key:
                raise HTTPException(status_code=400, detail="请输入 API Key")

            models = await asyncio.to_thread(
                test_deepseek_connection, api_key, model_name, url
            )
            return {
                "status": "ok",
                "message": "连接成功",
                "models": models,
            }

        elif provider == "ollama":
            if not url:
                url = "http://127.0.0.1:11434"

            def _ollama_check(ollama_url):
                import urllib.request
                import json as json_lib

                req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        data = json_lib.loads(resp.read().decode("utf-8"))
                        return [m["name"] for m in data.get("models", [])]
                return []

            try:
                models = await asyncio.to_thread(_ollama_check, url)
                if models:
                    return {
                        "status": "ok",
                        "message": "Ollama 服务连接成功",
                        "models": models,
                    }
                else:
                    raise HTTPException(status_code=400, detail="Ollama 未返回模型列表")
            except Exception as e:
                # Handle sub-exceptions properly
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(
                    status_code=400, detail=f"连接 Ollama 失败: {str(e)}"
                )
        else:
            raise HTTPException(status_code=400, detail="未知的 AI 提供商")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # 清理错误消息，移除过长的技术细节
        if (
            "litellm" in error_msg.lower()
            or "google" in error_msg.lower()
            or "deepseek" in error_msg.lower()
            or "http " in error_msg.lower()
        ):
            if "AuthenticationError" in error_msg or "401" in error_msg:
                error_msg = "API Key 无效或已过期"
            elif "PermissionDenied" in error_msg or "403" in error_msg:
                error_msg = "API Key 权限不足"
            elif "RateLimitError" in error_msg or "429" in error_msg:
                error_msg = "请求频率过高，请稍后再试"
            elif "NotFoundError" in error_msg or "404" in error_msg:
                error_msg = "模型不存在或 API 端点错误"
            elif "INVALID_ARGUMENT" in error_msg or "invalid" in error_msg.lower():
                error_msg = "API Key 格式无效"
            else:
                # 提取核心错误信息
                if ":" in error_msg:
                    error_msg = error_msg.split(":")[-1].strip()[:100]
        raise HTTPException(status_code=400, detail=error_msg)


# Cache for AI status to prevent constant blocking calls
_ai_status_cache = {"data": None, "time": 0}
_AI_STATUS_CACHE_TTL = 300  # 5 minutes


@app.get("/api/ai-status")
async def get_ai_status(verify: bool = False):
    """
    Check the status of all configured AI providers.
    By default this uses a lightweight status response: it only
    reports whether providers are configured and returns local model presets.
    Pass verify=true for an explicit live connection check.
    """
    config = load_config()

    if not verify:
        gemini_config = config.get("gemini", {})
        deepseek_config = config.get("deepseek", {})
        ollama_config = config.get("ollama", {})
        ollama_url = ollama_config.get("url", "http://127.0.0.1:11434")

        return {
            "gemini": {
                "configured": bool(gemini_config.get("api_key")),
                "connected": bool(gemini_config.get("api_key")),
                "verified": False,
                "models": DEFAULT_GEMINI_MODELS,
            },
            "deepseek": {
                "configured": bool(deepseek_config.get("api_key")),
                "connected": bool(deepseek_config.get("api_key")),
                "verified": False,
                "models": DEFAULT_DEEPSEEK_MODELS,
            },
            "ollama": {
                "configured": bool(ollama_url),
                "connected": bool(ollama_url),
                "verified": False,
                "models": [],
            },
        }

    now = time.time()
    if _ai_status_cache["data"] and (
        now - _ai_status_cache["time"] < _AI_STATUS_CACHE_TTL
    ):
        return _ai_status_cache["data"]

    # Define check functions for thread pool
    def check_gemini(conf):
        gemini_config = conf.get("gemini", {})
        status = {
            "configured": bool(gemini_config.get("api_key")),
            "connected": False,
            "models": [],
        }
        if status["configured"]:
            try:
                available_models = test_gemini_connection(
                    gemini_config["api_key"], gemini_config.get("model_name", "")
                )
                status["connected"] = True
                status["models"] = available_models[:10]
            except Exception as e:
                status["error"] = str(e)[:100]
        return status

    def check_deepseek(conf):
        deepseek_config = conf.get("deepseek", {})
        status = {
            "configured": bool(deepseek_config.get("api_key")),
            "connected": False,
            "models": [],
        }
        if status["configured"]:
            try:
                models = test_deepseek_connection(
                    deepseek_config["api_key"],
                    deepseek_config.get("model_name", ""),
                    deepseek_config.get("url") or deepseek_config.get("base_url", ""),
                )
                status["connected"] = True
                status["models"] = models
            except Exception as e:
                status["error"] = str(e)[:100]
        return status

    def check_ollama(conf):
        ollama_config = conf.get("ollama", {})
        ollama_url = ollama_config.get("url", "http://127.0.0.1:11434")
        status = {"configured": bool(ollama_url), "connected": False, "models": []}
        if status["configured"]:
            try:
                import urllib.request
                import json as json_lib

                req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        data = json_lib.loads(resp.read().decode("utf-8"))
                        status["connected"] = True
                        status["models"] = [m["name"] for m in data.get("models", [])]
            except Exception as e:
                status["error"] = str(e)[:100]
        return status

    # Run checks in parallel using threads to avoid blocking the main loop
    tasks = [
        asyncio.to_thread(check_gemini, config),
        asyncio.to_thread(check_deepseek, config),
        asyncio.to_thread(check_ollama, config),
    ]

    gemini_res, deepseek_res, ollama_res = await asyncio.gather(*tasks)

    result = {"gemini": gemini_res, "deepseek": deepseek_res, "ollama": ollama_res}

    # Update cache
    _ai_status_cache["data"] = result
    _ai_status_cache["time"] = now

    return result


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=18001)
