# 2026-05-21 流程优化与依赖核查记录

## 本轮目标

- 修复配置脱敏后，前端无法正确判断 Gemini/DeepSeek 已配置的问题。
- 优化入库和清理执行前的确认流程，降低误删和误覆盖风险。
- 增加可视化清理策略入口，方便维护默认保留数、排除关键词和排除目录。
- 核查直接依赖和本地虚拟环境依赖状态，保持打包版依赖精简。

## 流程优化记录

### AI 可用性判断

- 前端新增 `isAIProviderReady()`。
- Gemini/DeepSeek 使用 `/api/config` 返回的 `configured`/`api_key_masked` 判断是否已配置，不再依赖真实 `api_key` 字段。
- AI 开关打开但当前模型未配置时，不再中断“文件入库扫描”，而是提示后自动降级到本地规则扫描。

### 批量确认弹窗

- 抽出 `buildBatchPlan()`，统一生成转移、删除、受保护跳过和未选目标目录列表。
- 原生 `confirm()` 改为应用内确认弹窗。
- 弹窗展示：
  - 入库转移数量。
  - 旧版清理数量。
  - 受保护跳过数量。
  - 未选择目标目录数量。
  - 前几个待清理文件名。
- 同名覆盖改为弹窗内复选框。

### 清理策略设置

- 设置页新增“清理策略”标签。
- 复用现有 `/api/retention-rules` GET/PUT。
- 可维护：
  - `global_keep_latest`
  - `protected_keywords`
  - `protected_directories`
- 保存位置仍为 `~/.software_organizer/retention_rules.json`。
- 不修改单文件保留规则 `keep_rules.json`。

### 文件行可读性

- 清理计划/入库列表改为稳定网格布局。
- 文件名单独占主行，分类和“建议清理/保留”提示放到第二行，避免标签压住名称。
- 版本列使用固定最小宽度，空版本显示占位符，避免和目标目录互相挤压。
- 分组名、文件名、历史记录和目录选择补充 `title`，截断时可查看完整文本。

### AI 建议缓存

- 清理计划 AI 缓存 key 改为包含 `path`、`filename`、`version`、`size`、`mtime`。
- 避免同名文件、顺序变化或大小相同但路径不同的文件复用旧建议。

## 依赖核查

### 执行结果

```bash
python -m pip check
# No broken requirements found.

python -m pip list --outdated --format=json
```

核查结论：

- 当前虚拟环境有可升级包，但没有依赖冲突。
- 直接依赖使用 `>=` 范围，新环境安装时会解析到可用的新版本，不需要把版本固定死。
- `fastapi`、`uvicorn`、`pydantic`、`Pillow`、`pywebview`、`pyinstaller` 在当前虚拟环境中不是最新，但属于兼容范围内的常规更新，不建议在本轮和流程优化混在一起做大升级。
- `litellm`、`openai`、`ollama`、`google-generativeai`、`google-api-python-client` 等包出现在本地虚拟环境中，但不是核心打包依赖；打包配置仍显式排除这些可选 AI SDK。
- `backoff` 未被当前代码直接使用，已从 `requirements.txt` 移除。

### 当前依赖策略

- 核心运行：FastAPI、Uvicorn、Pydantic、pywebview。
- 构建打包：PyInstaller、Pillow。
- AI：Gemini、DeepSeek、Ollama 默认走 HTTP；自定义 LiteLLM Provider 才需要额外安装可选依赖。

## 验证记录

已执行：

```bash
node --check static/app.js
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m pip check
./scripts/build_standalone.sh
codesign --verify --deep --strict /Applications/FileOrganizer.app
```

前端烟测：

- 设置页“清理策略”标签可打开，默认保留数、排除关键词、排除目录三个输入区可见。
- 生成清理计划后，文件行使用新版网格布局，首行样式为 `display: grid`。
- 首个清理计划文件行验证到文件名 `title`、版本 `title` 和版本列固定宽度。
- `style.css?v=13` 和 `app.js?v=13` 已用于避免浏览器沿用旧静态资源缓存。

测试覆盖：

- 配置脱敏后仍保留 `configured` 字段。
- 无 API Key 时 `configured` 为 `false` 且不返回 `api_key`。
- 全局保留最近 2 版。
- 目录排除保护。
- 关键词排除保护。

安装版核验：

- `/Applications/FileOrganizer.app` 已覆盖安装。
- 安装版大小约 36M。
- 安装版启动后监听 `127.0.0.1:18001`。
- 安装版 `/api/config` 不返回真实 `api_key`。
- 安装版 `/api/retention-rules` 可返回全局保留策略。
- 安装版静态资源已包含 `style.css?v=13`、`app.js?v=13` 和新版文件行网格样式。
- 安装包内未发现 LiteLLM/OpenAI/Ollama/Google Generative AI 等可选 SDK 目录。
