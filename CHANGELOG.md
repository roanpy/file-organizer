# Changelog

## Unreleased

### Changed
- CI and release builds now install a hashed cross-platform dependency lock; Ruff runs as a required CI check.
- Routine Python Dependabot version PRs are disabled because they cannot safely refresh the reviewed lock and packaging evidence; security updates remain enabled.
- Documentation identifies Windows packaging as experimental and current macOS CI artifacts as arm64/ad-hoc signed.
- Packaged application logs rotate at 2 MiB with two backups and use owner-only permissions.

### Security
- Pinned CI and build actions to immutable commits and grouped future Actions updates.

## [1.5.1] - 2026-08-12

### Added
- GitHub issue forms, a pull request checklist, and monthly Dependabot updates for Python and Actions dependencies.
- CI syntax coverage for the localization script.

### Security
- `GET /api/ai-config` recursively removes credential-shaped fields from its response, covering legacy and custom configuration data.
- Public release metadata and security automation are aligned with the latest source commit.

## [1.5.0] - 2026-08-09

### Added
- English-first README with a Chinese guide, local system-language UI adaptation, and a source-first public release workflow.
- Current English and Chinese interface previews captured from isolated synthetic demo data.
- Public safety checks and explicit documentation for privacy boundaries, third-party licenses, contribution rules, security reports, and release gates.
- Third-party notices now cover the PyObjC, bottle, proxy_tools, and typing_extensions runtime dependencies bundled by pywebview; the English README links to the AI agent skill guide.
- Separate Windows PyInstaller configuration so Windows builds do not reuse the macOS application bundle configuration.
- macOS desktop language detection now prioritizes the native ordered language list, with Qt and environment values as fallbacks; `zh-Hans-US` remains Chinese under `C.UTF-8`.
- Dependency verification refreshed the local build environment to FastAPI 0.141.1, Uvicorn 0.52.1, Pydantic 2.13.4, Pillow 12.3.0, pywebview 6.2.1, and PyInstaller 6.22.0 within the declared ranges.

### Fixed
- Dynamic interface text now follows the selected locale, including scan modes, file counts, version labels, cleanup decisions, and runtime notifications.
- Removed the unlicensed reference-code directory from the publishable Git index while leaving the local working copy untouched.
- Removed absolute local paths from batch AI path-suggestion prompts; directory IDs are resolved back to local paths only on the local machine.
- `GET /api/ai-config` now recursively removes credential-shaped fields, so legacy or custom AI configuration cannot expose stored keys even if it contains them.
- Fixed the public license attribution so the standalone project no longer carries the earlier reference project's copyright line.

### Release Boundary
- Provider keys, local configuration, logs, databases, model files, caches, shell or agent configuration, and unsigned local build artifacts are not part of the public source release.

## [1.4.1] - 2026-07-18

### Fixed
- 修复带点号的产品名被误当作文件扩展名截断的问题，避免 `PDF.Converter`、`SQLPro.Studio` 等不同产品因退化为厂商前缀而被错误归组和列入清理候选。
- Web 启动脚本不再强制结束占用 18001 端口的进程，改为复用健康服务或自动选择 18002-18050 的可用端口。

### Changed
- 删除分类和还原默认分类改用统一的应用内确认弹窗；主要弹窗和图标按钮补充对话框语义、可访问名称、键盘退出与焦点恢复。

### Tests
- 新增点号产品名隔离测试，并用实际配置目录执行只读清理计划回归检查。
- 完整运行单元测试、Ruff、Python 编译、前端语法、依赖和 macOS 应用打包核验。

## [1.4.0] - 2026-07-16

### Changed
- **名称匹配增强**: 新增软件名归一化匹配，自动忽略版本号、平台后缀、发布标签和常见分隔符差异，减少已有软件漏匹配。
- **AI 辅助降级优化**: AI 模式现在会把模型返回结果重新映射到真实扫描文件，并在 AI 未命中时继续使用本地路径推荐；不开启 AI 时核心扫描、匹配、查重、转移保持可用。
- **Gemini/DeepSeek 调用简化**: Gemini 和 DeepSeek 改为直接使用官方 HTTP API，不再依赖打包进 `google-generativeai`、`openai` 或 LiteLLM SDK。
- **清理计划升级**: 目标文件查重升级为清理计划，新增软件级保留策略（保留最近 N 个版本/永不清理），受保护版本不会被批量删除。
- **清理交互优化**: 查重结果现在会显示受保护数量、可清理数量、AI 建议原因，以及每个文件的保留/清理决策提示。
- **默认保留选择优化**: 入库分析结果按版本和修改时间推荐保留项，避免默认用旧下载文件覆盖较新的目标文件。
- **打包依赖简化**: 使用显式 PyInstaller 配置，AI SDK 改为运行时可选懒加载，核心应用不再强制打包 LiteLLM/OpenAI/Ollama/Gemini 依赖。
- **打包脚本校准**: 修正图标文件检查，并在 PyInstaller spec 中显式排除可选 AI SDK，避免发布包误带未使用依赖。
- **配置安全加固**: `/api/config` 默认不再返回真实 API Key，前端保存空 Key 时保留原配置，并收紧本地 API 的 CORS 策略。
- **Ollama 依赖修正**: Ollama 分析调用改为本地 HTTP API，不再依赖 `ollama` Python SDK。
- **仓库清理**: 移除误提交的运行时 `server.pid`，并加入忽略规则。
- **帮助文档完善**: 更新应用内使用说明、README 使用流程和批量处理文档，新增 2026-05-20 维护/打包/安全核验过程记录。
- **流程精细化优化**: 修复脱敏配置下 AI 已配置却被前端误判为不可用的问题；AI 未配置时自动降级到本地规则扫描。
- **批量确认优化**: 入库/清理执行前改为应用内确认弹窗，统一展示转移、清理、受保护跳过、未选目标和待清理文件预览。
- **清理策略入口**: 设置页新增“清理策略”，可维护全局默认保留版本数、排除清理关键词和排除清理目录。
- **文件行可读性优化**: 清理计划/入库列表改为稳定网格布局，文件名、决策标签、版本和目标目录不再互相挤压；历史记录和目录选择也补充完整悬停标题。
- **AI 状态检查调整**: 顶部 Gemini/DeepSeek 状态默认只判断是否已配置，不再后台轮询真实连接导致已配置模型误显示红点；实时连通性保留给“验证连接”按钮。
- **同名文件转移提示优化**: 未勾选“覆盖同名文件”时，目标已存在不再按普通失败展示，而是明确提示已跳过并引导在确认弹窗中手动开启覆盖。
- **相近名称防误匹配**: 收紧软件名相似度评分，避免 `open-codesign` 和 `open-design` 这类共享前缀但核心词不同的软件被误判为同一产品。
- **依赖整理**: 移除未使用的直接依赖 `backoff`，记录 2026-05-21 依赖核查结论。
- **文件分类文案统一**: 设置页和帮助文档从“软件格式/软件分类”调整为“文件格式/文件分类”，明确软件包只是默认分类之一，也可管理文档和资料。
- **应用名称调整**: 应用内标题和窗口标题改为 `File Organizer Pro`，macOS 打包产物改为 `FileOrganizer.app`；用户配置目录继续保留 `~/.software_organizer` 以兼容既有设置。
- **文档日期版本识别**: 文件名中的明确日期（如 `2026-06-25`、`20260625`）会作为版本排序依据；没有版本或日期时继续使用文件修改时间兜底。
- **文件操作安全边界**: 转移和删除接口仅允许操作用户已配置的源目录/目标目录，阻止越界路径进入批处理。
- **安全覆盖与失败保护**: 同名覆盖改为完整复制后原子替换；任何转移失败或同名跳过都会阻止本轮继续删除旧版本。
- **制品变体隔离**: 语言包、补丁、ARM64、Intel、Universal 分别分组，通用安装文件按所在目录隔离，避免将不同制品或不同软件误判为旧版本。
- **默认配置完善**: 新安装默认关闭 AI，并内置文档资料、Mac、iOS、Windows 和通用压缩包分类。
- **本地配置保护**: 配置和规则文件改为原子写入和仅当前用户可读，SQLite 连接在操作后显式关闭。
- **发布流程修复**: GitHub Actions 使用 `FileOrganizer` 产物路径，移除未打包 AI SDK 的无效安装和清理步骤，并为直接依赖增加兼容主版本上限。
- **构建环境解耦**: 打包配置显式排除仅因本地虚拟环境存在而被发现的 Tenacity、python-dotenv 和 PyYAML，保证本地与干净 CI 产物一致。
- **网络目录响应性**: 扫描、分析、目录浏览和文件操作路由交由 FastAPI 线程池执行，慢速或离线网络盘不再阻塞健康检查和其他界面请求。
- **依赖升级**: 验证 FastAPI 0.139.0、Uvicorn 0.51.0、Pydantic 2.13.4、Pillow 12.3.0、pywebview 6.2.1 和 PyInstaller 6.21.0。
- **独立 Skill 安全同步**: Skill 改为先转移后清理，增加目录边界和安全覆盖，回收站失败时不再回退为永久删除。

### Tests
- 新增匹配规则单元测试，覆盖紧凑软件名、通用压缩包跨格式匹配、相近 Adobe 产品防误匹配，以及 `open-codesign`/`open-design` 防串台。
- 新增文档日期解析测试，覆盖分隔符日期和紧凑日期文件名。
- 新增 AI HTTP 调用和保留策略单元测试，覆盖打包版 Gemini/DeepSeek 调用路径与最近版本保护策略。
- 新增配置脱敏测试，覆盖 API Key 不回传与空 Key 保存不覆盖旧配置。
- 扩展保留策略测试，覆盖全局保留 2 版、目录排除和关键词排除。
- 新增安全覆盖、目录边界、默认配置、端口识别和制品变体测试；全仓库 Ruff、Python 编译和前端语法检查纳入发布核验。

### ✨ 新增功能 (New Features)
- **AI Agent Skill 提取**: 全新封装 `SoftwareOrganizer-Skill`，赋予外部 AI Agent (Claude Code/OpenClaw 等) 管理和整理软件包的能力。
  - 提供 CLI 解析接口，支持外部 AI 进行分析和决策填入。
  - 支持通过环境变量（`SOFTWARE_ORGANIZER_APP_DIR`）独立配置和运行，自动复用后端 API。
- **CLI 接口优化**: 完善 `SoftwareOrganizer-Skill` 的 CLI 调用逻辑，提升 Agent 的协同精度。
- **环境适配优化**: 增强 Skill 的环境感知，支持在不同工作目录下独立加载应用逻辑，解耦核心库依赖。

## [1.3.0] - 2026-03-24

### ⚡️ 优化 (Optimizations)
- **默认端口调整**: 将默认服务端口从 `8001` 更改为 `18001`，以避免常见端口冲突。
- **端口自动切换**: 增强了端口占用检测逻辑，若 `18001` 被占用，将自动向上寻找可用端口。

## [1.2.1] - 2026-01-27

### Added
- **GitHub Workflows**: Added CI/CD pipeline for automated Windows and Mac builds.
- **Build Scripts**: Standardized Windows build script to use `SoftwareOrganizer.spec`.

### Fixed
- **UI**: Fixed an issue where "Cross-Format Match" toggle and "Restore" buttons in settings were unclickable.

## [1.2.0] - 2026-01-27

### ✨ 新增功能 (New Features)
- **分组移除功能**: 支持在分析结果中临时移除不需要处理的分组（点击分组标题栏的🗑️图标）。
  -移除后该组及其文件将不参与批量处理。
  - 此操作为临时性的（刷新后恢复），不会删除磁盘文件。

## [1.1.1] - 2026-01-22

### ⚡️ 优化 (Optimizations)
- **智能路径推荐强化**: 优化了无精确匹配时的路径推荐算法，切换至绝对路径处理，并引入品牌关键词加权评分机制，显著提升了冷启动场景下的推荐准确度。
- **匹配策略稳健化**: 改进了 Level-1 目录的判定逻辑，支持基于绝对路径的递归匹配，解决了某些子目录下文件路径解析不一致的问题。
- **AI 引擎稳定性**: 优化了引擎配置读取逻辑，并对内置引擎（Gemini/DeepSeek/Ollama）采用 Native SDK 优先直连模式，提升了在高并发或网络波动下的响应可靠性。

## [1.1.0] - 2026-01-19

### ✨ 新增功能 (New Features)
- **跨格式查重 (Cross-Format Matching)**: 支持忽略扩展名差异的去重（如 .dmg 与 .pkg），可在设置中按分类开启。
- **按钮交互优化**: 移除"清理/批量"按钮的禁用状态，始终可点击并提供明确的空状态提示。

### 🐛 缺陷修复 (Bug Fixes)
- **数据安全**: 修复批量处理中"转移并覆盖"时的逻辑漏洞，防止因目标文件在删除列表中而导致新文件被误删。
- **状态同步**: 修复 Keep 规则与 UI 状态的同步问题。
- **版本解析**: 修复了 `Path Finder` 等软件因特殊版本号格式（如 `v2211`）无法识别，导致查重功能失效和 AI 分析回退的问题。

### ⚡️ 优化 (Optimizations)
- **AI 性能优化**: 引入"规则预筛选" (Pre-filtering) 机制，仅将未匹配软件发送给 AI 分析。
- **智能路径推荐**: 新增品牌匹配与分类匹配双重策略。
- **离线能力**: 移除外部 CDN，实现完全本地化运行。

### 🧹 代码清理 (2026-01-16)
- **移除重复函数**: 删除 `server.py` 中重复定义的 `get_history` 路由
- **修复未使用变量**: `main.py` 中 `window` → `_window`, `server.py` 中 `unconfigured` → `_unconfigured`
- **更新 README**: 通用化安装路径，移除硬编码本地路径
- **更新 .gitignore**: 新增 `releases/` 目录和本地配置文件排除

### ✨ 新功能
- **帮助按钮**: 新增程序内帮助说明，包含快速上手流程、核心功能说明、分类管理说明、批量处理说明和实用技巧
- **构建优化**: 采用显式构建清理逻辑，移除 500+ 个无用的 Google API 定义文件，包体积减少约 90MB (220MB -> 130MB)

### Added
- **目标文件查重**：新增独立的查重功能，扫描目标目录中的重复/相似版本软件，支持一键清理旧版本。
  - 基于本地文件名分析，无需调用 AI
  - 自动勾选最新版本保留，支持持久化用户选择
- **UI 模式指示器**：在统计栏显示当前操作模式（AI 分析模式 / 查重模式）
- **智能 Keep 规则**：支持基于文件名的保留规则记忆。现在系统可以精确记住您希望保留的特定旧版本软件（如 `PullTube.v1.0.dmg`），即使文件被移动或重新扫描，只要文件名一致即可自动保留。
- **持久化模块**：新增 `persistence.py` 用于管理用户偏好设置（如 Keep 规则）。

### Changed
- **性能优化**：重构 AI 模型状态检查策略。
  - 页面加载延迟 2 秒执行初始检查，避免阻塞首屏。
  - 仅在展开下拉菜单时刷新所有引擎状态。
  - 后台轮询精准化：仅检查当前选中引擎（30秒/次），大幅减少无效请求。
- **视觉风格**：核心操作按钮回归浅色半透明风格（Light Style），增强界面通透感与玻璃拟态效果。
- **AI 分析优化**：对于超大文件列表引入智能筛选机制。
  - 源文件超过 80 个时自动截断
  - 目标文件超过 150 个时，根据源文件名称关键词智能预筛选相关文件，而非简单截断前 150 个
- **警告抑制**：抑制 `google.generativeai` 库的废弃警告，保持控制台清洁
- **路径选择优化**：源文件转移时的目标路径选择现在更加智能。
  - 后端直接返回匹配项的绝对路径，消除路径拼接错误。
  - 前端下拉菜单现在能正确显示并默认选中最佳匹配（如 `Tools (Mac)/AppName/`），支持多层级子目录。
  - 优化了下拉选项的去重和显示格式。
- **Keep 规则存储**：从仅支持 "软件名" 升级为优先支持 "文件名"（含版本）和 "文件路径"，实现了版本敏感的配置记忆。

### Fixed
- 修复了转移文件时默认路径总是回退到分类根目录（如 `Tools (Mac)`）的问题。现在能正确跟随匹配到的已安装软件路径。
- 修复了 Keep 规则保存时的参数错误（422 Unprocessable Content）。

---

## [Initial Version] - 2026-01-01

- 建立基础的 Mac/iOS 软件包管理功能
- 集成 AI 智能分析与版本分组
