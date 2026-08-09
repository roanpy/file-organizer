---
name: manage-software
description: 管理文档和软件包，执行扫描、AI 决策生成、分类与清理，并复用 File Organizer 配置。
---

# Manage Software Skill

## 架构原则

**Python 负责扫描和执行，AI 只做判断。**

流程：
1. `scan` → 扫描源目录软件列表
2. `analyze` → 生成 `~/.software_organizer-skill/decisions.json`
3. AI agent 读取 JSON，填入每个条目的 `decision` 字段
4. `execute` → Python 解析 decisions.json，执行转移/删除

## 快速开始

```bash
 cd <repo-root>/SoftwareOrganizer-Skill/skills/manage-software

python SKILL_CLI.py status    # 查看配置
python SKILL_CLI.py scan      # 扫描源目录
python SKILL_CLI.py analyze   # 生成 decisions.json
# AI agent 读取并填入 decision
python SKILL_CLI.py execute   # 执行决策
```

## 命令

| 命令 | 说明 |
|---|---|
| `status` | 服务状态、配置、分类 |
| `scan` | 扫描源目录，列出受支持文件 |
| `analyze` | 生成 decisions.json（含未分类 + 重复组） |
| `execute [--yes]` | 读取 decisions.json 执行 transfer/delete |

## 配置文件

- 读取 `~/.software_organizer/software_organizer_config.json`（app 现有配置）
- 环境变量 `SOFTWARE_ORGANIZER_CONFIG` 可覆盖路径
- File Organizer 源码默认位于仓库根目录；也可用兼容环境变量 `SOFTWARE_ORGANIZER_APP_DIR` 指定

## decisions.json 格式

```json
{
  "decisions": [
    {
      "type": "classify",
      "filename": "BetterTouchTool.v5.155.dmg",
      "file_path": "/path/to/Downloads/BetterTouchTool.v5.155.dmg",
      "size": "31.4 MB",
      "available_categories": {
        "mac": {"name": "Mac", "target_dir": "/path/to/Mac/"},
        "ios": {"name": "iOS", "target_dir": "/path/to/iOS/"}
      },
      "decision": {
        "action": "transfer",
        "target_dir": "/path/to/Mac/",
        "reason": "..."
      }
    },
    {
      "type": "dedup",
      "software_name": "Parallels.Desktop (.dmg) - Mac",
      "versions": [
        {"filename": "Parallels.v26.3.0.dmg", "file_path": "/.../v26.3.0.dmg", "version": "26.3.0", "size": "235.9 MB"},
        {"filename": "Parallels.v26.2.1.dmg", "file_path": "/.../v26.2.1.dmg", "version": "26.2.1", "size": "196.6 MB"}
      ],
      "decision": {
        "keep_file_path": "/.../v26.3.0.dmg",
        "delete_file_paths": ["/.../v26.2.1.dmg"],
        "reason": "保留更高版本"
      }
    }
  ]
}
```

## AI Agent 用法示例

```
用 manage-software skill:
1. scan 扫描 Downloads 目录
2. analyze 生成 decisions.json
3. 读取文件，对每个重复软件包判断保留哪个版本
4. 填入 decision 字段后保存
5. execute 执行删除
```

## 文件位置

```
SoftwareOrganizer-Skill/
├── skills/manage-software/
│   ├── SKILL.md          ← 本文件
│   └── SKILL_CLI.py     ← CLI 入口
├── scripts/
│   ├── check-server.py
│   └── start-server.py
└── src/
    ├── api_client.py
    ├── config_manager.py
    └── ai_helper.py       ← 生成/解析 decisions.json
```
