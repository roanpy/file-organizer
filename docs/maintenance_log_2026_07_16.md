# 2026-07-16 全面审查、安全优化与发布记录

## 审查结论

- 无 AI 时扫描、匹配、清理计划和转移流程保持完整可用；新安装默认关闭 AI。
- Gemini 与 DeepSeek 使用现有本地配置完成真实连接验证，未输出或提交 API Key。
- 直接依赖通过 `pip check`；已升级到兼容范围内最新版本：FastAPI 0.139.0、Uvicorn 0.51.0、Pydantic 2.13.4、Pillow 12.3.0、pywebview 6.2.1、PyInstaller 6.21.0。打包版继续排除可选 AI SDK。
- Git 历史和当前跟踪文件未发现 Gemini/DeepSeek/OpenAI 格式的真实密钥。

## 本轮修复

- 同名覆盖先复制到目标目录临时文件，完整写入后再原子替换；失败时保留旧目标和源文件。
- 批处理中只要出现转移失败或同名跳过，就跳过本轮全部旧版删除。
- 后端限制转移只能从已配置源目录进入已配置目标目录，删除只能操作已配置目标目录。
- 语言包、补丁、ARM64、Intel、Universal 分别分组；`setup`、`installer` 等通用名称按所在目录隔离。
- 配置和规则文件使用原子写入并设置为 `0600`，配置目录设置为 `0700`。
- SQLite 连接在每次操作后显式关闭，删除历史不再重复记录。
- 后端增加稳定健康标识，端口扫描覆盖 `18001-18050`，不再把任意 JSON 服务误认成本应用。
- GitHub Actions 更新为 `FileOrganizer` 产物路径，构建脚本删除重复依赖安装和无效 Google SDK 清理。
- PyInstaller 显式排除未声明且未使用的 Tenacity、python-dotenv、PyYAML，避免本地历史环境污染发布包。
- 阻塞型文件系统路由改由 FastAPI 线程池调度，避免网络目录 `scandir` 等待时冻结整个本地 API。
- 独立 Skill 同步目录边界和安全覆盖规则，改为先转移后清理；回收站失败时不再永久删除文件。
- 独立 Skill 的端口识别改用 `/api/health`，覆盖 `18001-18050`，启动时将选定端口明确传给 Uvicorn。

## 验证记录

- 项目 `.venv` 中运行 `python -m unittest discover -s tests -v`：48 项通过（同时将 `ResourceWarning` 提升为错误）。
- 项目 `.venv` 中运行 `ruff check src tests SoftwareOrganizer-Skill`：通过。
- `node --check static/app.js`、`compileall`、项目 `.venv` 的 `pip check`、`git diff --check`：通过。
- 真实目标目录只读审查：清理分组由 100 个收敛为 91 个；跨目录 `setup.exe`/`7z` 误分组消失，LibreOffice 主程序与语言包分开管理。
- 浏览器验收：91 个分组、85 个清理候选；候选行名称和信息列呈变暗状态，确认弹窗数量一致，控制台无错误。
- Skill 真实启动验收：在 `18001` 启动并返回正确健康标识，检查脚本识别成功，测试进程随后停止。

## 发布核验

- 使用 PyInstaller 6.21.0 构建 `File Organizer 1.4.0`，产物为 Apple Silicon (`arm64`) 应用，大小约 36 MB。
- `codesign --deep --strict` 验证通过；发布包未包含可选 AI SDK、Tenacity、python-dotenv 或 PyYAML。
- 已覆盖安装到 `/Applications/FileOrganizer.app`，旧 `/Applications/SoftwareOrganizer.app` 不存在。
- 安装版启动后 `/api/health` 返回正确标识；清理扫描返回 91 个分组，扫描期间连续健康检查均在 1 ms 内响应。
- 安装版 `/api/config` 验证默认 AI 为关闭状态，且接口未返回真实 API Key。
- 发布验证完成后停止测试进程，并清理开发目录中的 `build/`、`dist/`、`.app` 和 Python 缓存产物。
