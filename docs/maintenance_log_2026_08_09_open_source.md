# 2026-08-09 开源准备与公开发布记录

## 目标

将项目整理为 `file-organizer`，以 `File Organizer Pro` 作为应用名称，保留 `~/.software_organizer` 用户配置兼容性，并以源码优先方式公开发布。

## 已核查

- 初始审计时工作树无未提交改动，`master` 与私有远端提交一致；本轮公开整理产生的改动不直接覆盖旧私有历史。
- 用户配置、历史记录、数据库、日志和 API Key 位于本机 `~/.software_organizer/`，未被 Git 跟踪。
- 当前工作树和已有 Git 历史未发现常见 Gemini/DeepSeek/Bearer/私钥模式。
- 根目录已有 MIT License。
- 根目录许可证版权归属已改为当前独立项目的 `File Organizer contributors`，不再沿用参考项目的版权行。
- 当前仓库原名为 `SoftwareOrganizer`，GitHub 可见性为 Private，远端没有发布标签。

## 本轮处理

- 公开仓库改用 `file-organizer`，应用包和用户配置目录保持兼容。
- README 改为英文优先，并保留中文说明入口。
- 前端按系统语言自动选择中文或英文，不增加第三方翻译服务或前端框架。
- AI 批量路径建议只向模型发送本地目录 ID 和文件夹标签，绝对路径由本地服务映射。
- 增加公开安全扫描、贡献、安全、行为准则、第三方许可和发布文档。
- 将参考代码目录从公开 Git 索引中移出；本机保留副本，不在公开仓库发布无独立授权的参考代码。
- 拆分 Windows PyInstaller 配置，避免 Windows 构建复用 macOS `.app` bundle 配置。
- 增加 English-first README、系统语言适配、问题/系统特点说明，并同步中文文档。
- 修正桌面语言检测：macOS 优先读取 `AppleLanguages`，Qt 和环境变量只作跨平台兜底；增加 `zh-Hans-US + C.UTF-8` 回归测试，避免 Qt 只返回 `C` 时误显示英文。
- macOS 打包核验成功，产物签名校验通过，当前本地直接依赖已更新并验证为 FastAPI 0.141.1、Uvicorn 0.52.1、Pydantic 2.13.4、Pillow 12.3.0、pywebview 6.2.1 和 PyInstaller 6.22.0；未发现直接依赖仍有可用更新。
- 标签发布不再自动启动 Windows 构建；Windows 仅在手动工作流中显式勾选并完成目标系统验证后运行，避免取消或未验证的 Windows 任务把公开提交标成红叉。
- 补充开发协作说明：项目主要基于 OpenAI Codex 完成，其他 AI Agent 协助专项实现、审查、测试、文档和发布核验；关键变更与安全门槛仍由人工确认。
- GitHub Actions 的 checkout/setup-python 升级到 Node.js 24 运行时版本，消除旧 Node.js 20 弃用警告。
- 强化 `.gitignore` 和公开安全扫描，明确排除 `.zshrc`、Hermes/Pi/ZCode/Codex 配置、HF/API Token、`.env`、密钥、日志、数据库、模型和 KV/cache。

## 发布前门槛

1. 完整单元测试、Python 编译、前端语法、依赖和公开安全扫描通过。
2. macOS 和 Windows 构建配置分别验证。
3. 公开仓库只包含有授权的源码、静态资源和文档。
4. 公开前重新确认 GitHub 仓库可见性、默认分支、标签和 Actions 日志不含私密信息。

## 明确不公开的本机内容

- 用户主目录、挂载卷和网络盘中的真实路径；公开文档只允许不对应具体机器的通用占位符。
- `.zshrc`、Hermes/Pi/ZCode/Codex 配置，以及任何编辑器、Agent 或终端会话状态。
- HF/API Token、`.env`、私钥、证书、Cookie、运行日志、SQLite/JSON 运行数据。
- 模型文件、向量/键值缓存、下载的软件包、构建目录、`.app`/`.dmg`/`.exe` 和未完成授权核验的参考代码。
