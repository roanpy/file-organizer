# -*- coding: utf-8 -*-
"""
Config Manager - reads File Organizer's existing config files.

Supports multiple config locations:
1. File Organizer's own config file (software_organizer_config.json)
2. Environment variable override (SOFTWARE_ORGANIZER_CONFIG)
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any


CONFIG_DIR = Path.home() / ".software_organizer"
DEFAULT_CONFIG_NAME = "software_organizer_config.json"
SKILL_CONFIG_DIR = Path.home() / ".software_organizer-skill"
ENV_VAR = "SOFTWARE_ORGANIZER_CONFIG"


def _write_private_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, raw_temp_path = tempfile.mkstemp(prefix=".file-organizer-", dir=path.parent)
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def find_config_path() -> Optional[Path]:
    if env_path := os.environ.get(ENV_VAR):
        p = Path(env_path)
        if p.exists():
            return p

    paths = [
        CONFIG_DIR / DEFAULT_CONFIG_NAME,
        Path.home() / ".software_organizer.json",
        Path.home() / "SoftwareOrganizer" / DEFAULT_CONFIG_NAME,
    ]

    for p in paths:
        if p.exists():
            return p

    return None


def ensure_config() -> tuple[Dict[str, Any], Path]:
    config_path = find_config_path()
    if config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f), config_path

    SKILL_CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(SKILL_CONFIG_DIR, 0o700)
    skill_config_path = SKILL_CONFIG_DIR / DEFAULT_CONFIG_NAME

    if skill_config_path.exists():
        os.chmod(skill_config_path, 0o600)
        with open(skill_config_path, "r", encoding="utf-8") as f:
            return json.load(f), skill_config_path

    default_config = {
        "source_dir": "",
        "target_dir": "",
        "categories": {
            "mac": {
                "name": "Mac",
                "formats": [".dmg", ".pkg", ".zip", ".7z", ".rar"],
                "target_dir": "",
            },
            "ios": {"name": "iOS", "formats": [".ipa"], "target_dir": ""},
            "windows": {
                "name": "Windows",
                "formats": [".exe", ".msi"],
                "target_dir": "",
            },
            "documents": {
                "name": "文档资料",
                "formats": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".epub"],
                "target_dir": "",
            },
            "general": {"name": "通用格式", "formats": [".zip", ".rar", ".7z", ".tar", ".gz"], "target_dir": ""},
        },
        "current_engine": "gemini",
        "use_ai": False,
    }

    _write_private_json(skill_config_path, default_config)

    print("[Skill] 配置文件未找到，已在以下位置创建默认配置：")
    print(f"  {skill_config_path}")
    print("请编辑该文件，填入 source_dir（源目录）和 target_dir（目标目录）")
    print("或直接在 File Organizer 界面中配置，skill 会自动读取。\n")

    return default_config, skill_config_path


def load_config() -> Dict[str, Any]:
    config_path = find_config_path()
    if not config_path:
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_source_dir(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if config is None:
        config = load_config()
    return config.get("source_dir")


def get_target_dir(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if config is None:
        config = load_config()
    return config.get("target_dir")


def get_categories(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if config is None:
        config = load_config()
    return config.get("categories", {})


def get_current_engine(config: Optional[Dict[str, Any]] = None) -> str:
    if config is None:
        config = load_config()
    return config.get("current_engine", "gemini")


def get_software_organizer_root() -> Optional[Path]:
    if env_dir := os.environ.get("SOFTWARE_ORGANIZER_APP_DIR"):
        p = Path(env_dir)
        if (p / "src" / "main.py").exists() or (p / "src" / "server.py").exists():
            return p

    root = Path.cwd()
    if (root / "src" / "main.py").exists() or (root / "src" / "server.py").exists():
        return root
    skill_root = root
    for _ in range(3):
        skill_root = skill_root.parent
        if (skill_root / "src" / "main.py").exists() or (skill_root / "src" / "server.py").exists():
            return skill_root
    return None
