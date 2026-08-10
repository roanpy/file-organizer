# 🗺️ File Organizer Pro 项目结构

## 📂 根目录

| 文件/目录 | 类型 | 描述 |
|-----------|------|------|
| `README.md` | 文档 | 英文优先的项目主文档 |
| `README.zh-CN.md` | 文档 | 中文使用与维护说明 |
| `LICENSE` | 法律 | MIT 开源许可证 |
| `SECURITY.md` / `CONTRIBUTING.md` | 文档 | 安全报告与贡献规则 |
| `CODE_OF_CONDUCT.md` / `RELEASING.md` / `THIRD_PARTY_NOTICES.md` | 文档 | 行为准则、发布流程、第三方许可声明 |
| `requirements.txt` | 配置 | Python 依赖 |
| `SoftwareOrganizer.spec` | 配置 | macOS PyInstaller 配置，产物为 `FileOrganizer.app` |
| `SoftwareOrganizer.windows.spec` | 配置 | Windows PyInstaller 配置，产物为 `FileOrganizer/FileOrganizer.exe` |
| `SoftwareOrganizer-Skill/` | 目录 | **[新增]** 独立的 AI Agent Skill 模块，兼容 Claude Code/OpenClaw。 |
| `docs/` | 目录 | 批量处理、维护过程、打包核验等说明文档 |
| `.github/workflows/` | 目录 | GitHub Actions：提交检查与多平台构建 |

---

## 📂 源代码 (src/)

### 主文件

| 文件 | 描述 |
|------|------|
| `src/main.py` | **桌面入口** - 启动本地服务、选择端口并创建 pywebview 窗口 |
| `src/server.py` | **Web 服务器** - FastAPI REST API |

### software_organizer 包

| 模块 | 描述 |
|------|------|
| `__init__.py` | 包入口 |
| `config.py` | **配置管理** - 路径、格式、AI 配置 |
| `file_ops.py` | **文件操作** - 文件扫描、版本解析 |
| `ai_engines.py` | **AI 引擎** - Gemini/DeepSeek/Ollama 调用 |
| `transfer.py` | **转移管理** - 移动、删除文件 |
| `database.py` | **数据库** - SQLite 记录管理 |
| `persistence.py` | **持久化** - 手动保留规则、分组级保留策略与偏好设置 |

---

## 📂 前端界面 (static/)

| 文件 | 描述 |
|------|------|
| `index.html` | 主页面结构 |
| `app.js` | 前端业务逻辑 |
| `i18n.js` | 根据系统语言在中文/英文之间适配界面 |
| `style.css` | 样式表 |
| `ai_styles.css` | AI 建议与状态样式 |
| `favicon.png` | 网站图标 |
| `icon.icns` | macOS 应用图标 |
| `vendor/fontawesome/` | 本地打包的 Font Awesome Free 静态资源 |

---

## 📂 脚本 (scripts/)

| 文件 | 描述 |
|------|------|
| `start_web.sh` | 启动 Web 服务器 |
| `build_standalone.sh` | 构建 macOS `.app` 应用 |
| `build_windows.bat` | 构建 Windows 应用 |
| `check_public_safety.py` | 公开仓库常见泄密模式扫描 |

---

## 📂 测试 (tests/)

| 文件 | 描述 |
|------|------|
| `test_matching_rules.py` | 名称归一化、跨格式匹配、防误匹配测试 |
| `test_ai_http_engines.py` | Gemini/DeepSeek/Ollama HTTP 调用测试 |
| `test_retention_rules.py` | 历史版本保留策略测试 |
| `test_config_security.py` | 配置脱敏与 Key 保留测试 |
| `test_config_defaults.py` | 默认分类、AI 默认状态和私有配置权限测试 |
| `test_operation_safety.py` | 转移/删除目录边界测试 |
| `test_startup.py` | 后端识别与端口范围测试 |
| `test_skill_safety.py` | 独立 Skill 的目录边界测试 |
| `test_database.py` | SQLite 提交和连接关闭测试 |

---

## 📂 文档 (docs/)

| 文件 | 描述 |
|------|------|
| `batch_processing_logic.md` | 入库整理、清理计划、保留策略处理逻辑 |
| `images/` | 中英文界面预览截图（合成演示数据） |
| `maintenance_log_2026_05_20.md` | 清理计划、安全加固、依赖打包与发布核验过程 |
| `maintenance_log_2026_05_21.md` | 流程精细化优化、依赖核查与验证记录 |
| `maintenance_log_2026_07_16.md` | 全面审查、文件安全、分组保护与发布核验记录 |
| `maintenance_log_2026_08_09_open_source.md` | 开源整理、隐私边界、授权和公开发布门槛 |
| `optimization_and_refactor_2026_01_12.md` | 早期性能优化与重构记录 |

## 不进入公开仓库的内容

- `~/.software_organizer/` 下的配置、API Key、历史、数据库和日志。
- `.env`、Shell/Agent 配置、模型文件、KV/cache、临时文件和本地构建产物。
- `releases/` 下的参考代码或未完成授权核验的本地材料。

---

## 📂 数据存储

配置和历史记录存储于 `~/.software_organizer/`：

| 文件 | 描述 |
|------|------|
| `software_organizer_config.json` | 用户配置 |
| `software_organizer_history.json` | 操作历史 |
| `software_organizer.db` | SQLite 数据库 |
| `keep_rules.json` | 单文件保留/取消保留规则 |
| `retention_rules.json` | 分组级历史版本保留策略 |
