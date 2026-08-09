# SoftwareOrganizer-Skill

用于管理文档和软件包的 AI agent skill，可复用 **File Organizer** 配置与本地后端。

兼容：Claude Code、OpenClaw (Antigravity)、OpenCode 及所有 AI 编码 agent。

## 功能特点

- **自动检测端口**（18001-18050），通过健康标识复用已运行的 File Organizer
- **读取现有配置**，无需重新配置
- **AI 辅助决策**，对重复/未分类软件给出判断
- **操作前复核**，所有危险操作（删除/转移）需确认
- **无需 GUI**，纯 CLI/API 运行

## 目录结构

```
SoftwareOrganizer-Skill/
├── README.md
├── skills/
│   └── manage-software/
│       ├── SKILL.md        ← AI agent 技能定义
│       └── SKILL_CLI.py   ← CLI 主入口
├── scripts/
│   ├── check-server.py    ← 检查服务状态
│   └── start-server.py    ← 自动启动/复用后端服务
└── src/
    ├── api_client.py       ← HTTP 客户端
    ├── config_manager.py   ← 读取 app 配置
    └── ai_helper.py        ← 生成决策上下文
```

## 配置说明

无需额外安装，只需确保：

 1. File Organizer 应用源码位于该 skill 目录外两层（即默认克隆结构）。如果单独下载了该 skill，请设置兼容环境变量 `SOFTWARE_ORGANIZER_APP_DIR` 指向应用根目录。
 2. 配置文件位于 `~/.software_organizer/software_organizer_config.json`（app 自动生成，或首次手动配置）。
 3. 如有需要也可以通过配置环境变量 `SOFTWARE_ORGANIZER_CONFIG` 来指定配置文件路径。

## 使用方法

```bash
cd <repo-root>/SoftwareOrganizer-Skill/skills/manage-software

# 查看状态
python SKILL_CLI.py status

# 扫描源目录
python SKILL_CLI.py scan

# AI 分析准备（生成 decisions.json）
python SKILL_CLI.py analyze

# 执行已填好的决策
python SKILL_CLI.py execute --yes
```

## 工作流程

```
1. scan    → 扫描源目录，列出所有受支持文件
2. analyze → 生成 ~/.software_organizer-skill/decisions.json
              每个条目包含：file_path、版本、大小、AI 决策字段（留空）
3. AI 填入 decision 字段（参考下方格式）
4. execute → Python 读取 decisions.json，执行转移/删除
```

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
        "mac": {"name": "Mac", "formats": [".dmg", ".pkg"], "target_dir": "/path/to/Mac/"},
        "ios": {"name": "iOS", "formats": [".ipa"], "target_dir": "/path/to/iOS/"}
      },
      "decision": {
        "action": "transfer",
        "target_dir": "/path/to/Mac/",
        "reason": "BetterTouchTool 是 Mac 软件"
      }
    },
    {
      "type": "dedup",
      "software_name": "Parallels.Desktop (.dmg) - Mac",
      "versions": [
        {"filename": "Parallels.Desktop.v26.3.0.dmg", "file_path": "...", "version": "26.3.0", "size": "235.9 MB"},
        {"filename": "Parallels.Desktop.v26.2.1.dmg", "file_path": "...", "version": "26.2.1", "size": "196.6 MB"}
      ],
      "decision": {
        "keep_file_path": "/.../Parallels.Desktop.v26.3.0.dmg",
        "delete_file_paths": ["/.../Parallels.Desktop.v26.2.1.dmg"],
        "reason": "保留更新版本 26.3.0"
      }
    }
  ]
}
```

## AI Agent 使用示例

告诉 AI agent：

> "用 manage-software skill 扫描 Downloads 目录，运行 analyze 生成 decisions.json，然后读取文件对每个重复软件包填入保留/删除决定，最后运行 execute 执行。"

## 环境要求

- Python 3.10+
- File Organizer 后端服务（未运行时自动启动）
