# -*- coding: utf-8 -*-
"""
software_organizer 包 - 文件、文档和软件包管理工具

提供软件扫描、AI 分析、版本识别和智能转移功能。
仅用于 Web 服务器模式。
"""

from .config import (
    APP_DIR,
    CONFIG_FILE,
    HISTORY_FILE,
    AI_CONFIG_FILE,
    load_config,
    save_config,
    load_ai_config,
    save_ai_config,
    get_default_ai_config,
    load_history,
    save_history,
    save_history_item,
    get_historical_transfers,
)

from .file_ops import (
    scan_software,
    get_target_directories,
    parse_software_name,
)

from .ai_engines import (
    analyze_software_relation,
    suggest_destination,
)

from .transfer import (
    move_software,
    delete_software,
)

from .database import SoftwareDB, get_db

__all__ = [
    # Config
    "APP_DIR",
    "CONFIG_FILE",
    "HISTORY_FILE",
    "AI_CONFIG_FILE",
    "load_config",
    "save_config",
    "load_ai_config",
    "save_ai_config",
    "get_default_ai_config",
    "load_history",
    "save_history",
    "save_history_item",
    "get_historical_transfers",
    # File Operations
    "scan_software",
    "get_target_directories",
    "parse_software_name",
    # AI
    "analyze_software_relation",
    "suggest_destination",
    # Transfer
    "move_software",
    "delete_software",
    # Database
    "SoftwareDB",
    "get_db",
]

__version__ = "1.5.1"
