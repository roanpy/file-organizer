# 2026-05-20 清理计划、安全加固与打包核验记录

## 背景

本轮维护围绕三个目标展开：

- 提升已有软件名称匹配的容错能力，减少因版本号、平台后缀、发布标签、分隔符不同导致的漏匹配。
- 让 AI 模式真正成为“辅助增强”，在目录推荐、未匹配项分析、清理建议中发挥作用，同时保证 AI 关闭时核心流程仍可用。
- 完整核实打包依赖、本地配置安全和 GitHub 提交内容，避免把用户配置或运行时文件提交到仓库。

## 功能调整记录

### 帮助与维护文档

本轮同步更新了三类说明：

- 应用内帮助：补充 AI 可选、清理计划、历史版本保留、本地配置与密钥处理说明。
- README：补充文件入库扫描、生成清理计划、本地配置路径、维护文档入口。
- 批量处理逻辑文档：区分“文件入库扫描”和“生成清理计划”，明确勾选状态、保护规则、AI 参与边界和相关接口。

### 清理计划

原“目标文件查重”升级为“生成清理计划”：

- 目标目录重复项按版本、修改时间和大小排序。
- 默认保留最近 1 个版本。
- 每个分组显示受保护数量、可清理数量和保留原因。
- 批量处理时强制跳过受保护版本。

### 历史版本保留

新增结构化保留策略：

- `保留2版`：按软件保留最近 2 个版本。
- `永不清理`：该软件所有版本都不进入自动清理队列。
- `取消策略`：恢复全局默认策略。
- 手动锁定仍按单文件规则保存，适合精确保留某个版本。

策略文件位置：

- `~/.software_organizer/keep_rules.json`
- `~/.software_organizer/retention_rules.json`

### AI 调用与降级

内置 AI 引擎统一走 HTTP：

- Gemini：Google Generative Language HTTP API。
- DeepSeek：OpenAI-compatible HTTP API。
- Ollama：本地 `/api/chat` HTTP API。

结果：

- 打包版不需要 `google-generativeai`、`openai`、`ollama`、`litellm` 这些 SDK。
- AI 调用失败时，本地规则仍然可以继续生成匹配和清理结果。
- AI 不覆盖手动保留规则，不建议删除受保护文件。

## 安全核验记录

### 本地配置

用户配置和运行数据保存在本机：

- `~/.software_organizer/software_organizer_config.json`
- `~/.software_organizer/software_organizer_history.json`
- `~/.software_organizer/software_organizer.db`
- `~/.software_organizer/keep_rules.json`
- `~/.software_organizer/retention_rules.json`
- `~/.software_organizer/app.log`
- `~/.software_organizer/server.log`

这些文件不属于仓库内容，不应提交到 GitHub。

### API Key 处理

已调整 `/api/config`：

- 默认不返回真实 `api_key`。
- 只返回 `configured` 和 `api_key_masked`。
- 前端保存模型配置时，如果 Key 输入框为空，会保留原有 Key。
- CORS 从通配开放改为拒绝跨站来源，避免其他网页直接读取本地 API。

### 仓库扫描

执行过的核查类型：

- 当前 HEAD 扫描真实 Key 模式：未发现。
- 当前 HEAD 扫描本机路径和内网 IP：未发现。
- 全 Git refs 扫描真实 Key 模式：未发现。
- 全 Git refs 扫描本机路径：仅发现历史提交中旧 README 出现过项目路径示例，不是密钥。

运行时文件清理：

- `server.pid` 已从仓库删除。
- `.gitignore` 已加入 `server.pid`。

## 打包核验记录

### 打包策略

使用 `scripts/build_standalone.sh` 和 `SoftwareOrganizer.spec` 构建 macOS `.app`。

打包配置重点：

- 显式包含 `static/`。
- 显式包含 FastAPI、Uvicorn、Pydantic、pywebview 和核心业务模块。
- 显式排除可选 AI SDK：LiteLLM、OpenAI、Ollama、Google Generative AI、googleapiclient。
- 构建后重新 ad-hoc 签名，避免优化后 bundle seal 失效。

### 已验证命令

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m pip check
./scripts/build_standalone.sh
codesign --verify --deep --strict /Applications/FileOrganizer.app
```

### 已验证结果

- 单元测试：11 个测试通过。
- Python 编译检查：通过。
- Python 依赖检查：通过。
- 安装包大小：约 36M。
- 安装位置：`/Applications/FileOrganizer.app`。
- 安装版启动后监听：`127.0.0.1:18001`。
- `/api/config`：不返回真实 Key。
- `/api/analyze/duplicates`：可返回清理计划和 `retention_summary`。
- 包内未发现可选 AI SDK 目录。

## 提交记录

- `3856a3f Improve cleanup planning and retention policies`
- `990c849 Harden config secrets and optional AI deps`

## 后续维护建议

- 如果未来加入新的 AI Provider，优先使用 HTTP API，只有确实需要 SDK 时才作为可选依赖。
- 如果需要发布给其他机器使用，应继续保持用户配置在 `~/.software_organizer/`，不要把本机目录写入默认配置。
- 如果用户认为历史提交里的本机路径也敏感，需要单独做 Git 历史重写；当前分支内容已经清理。
