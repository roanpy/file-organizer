# 性能优化与重构总结

## 修改日期
2026-01-12

## 修改概述
本次更新主要专注于后端性能优化、前端交互体验改进以及 AI 模型的稳定性增强。主要包括：AI 状态轮询策略重构、核心按钮样式回归、AI 分析大数据量防护以及废弃警告的抑制。

---

## 详细修改内容

### 1. 性能优化：AI 模型状态检查策略
**文件**: `static/app.js`

为了减少无效的 API 请求（此前为全量轮询），我们重构了状态检查逻辑：

- **冷启动优化**：页面加载后延迟 2 秒才执行首次全量检查，避免占用首屏渲染资源。
- **按需刷新**：
  - 仅在用户**点击下拉菜单**时，才触发全量所有引擎的状态检查。
  - **精准轮询**：后台定时器（30秒/次）**仅检查当前选中的引擎**状态，将请求量减少约 70%。
  - **页面可见性检测**：当页面不可见（tab 切换后台）时，自动暂停轮询。

```javascript
// 优化后的轮询逻辑
function startStatusPolling() {
    // ...
    statusPollingInterval = setInterval(() => {
        if (document.hidden) return; // 页面不可见时暂停
        checkSelectedEngineStatus(); // 仅检查当前选中项
    }, 30000);
}
```

### 2. 用户体验：按钮样式回归
**文件**: `static/style.css`, `static/index.html`

响应用户反馈，将核心操作按钮从"实心色块"风格还原为更具现代感的**浅色半透明（Light Style）**风格。

- **半透明背景**：使用 `rgba(r, g, b, 0.15)` 作为背景色。
- **细边框**：添加同色系 30% 透明度边框。
- **悬停效果**：加深背景透明度至 25% 并添加轻微上浮动画。
- 涉及按钮：AI 文件分析 (Blue), 目标文件查重 (Orange), 批量处理 (Green).

### 3. 稳定性：AI 分析大数据量防护
**文件**: `src/software_organizer/ai_engines.py`

针对大量文件分析时可能导致的 Token 超限（400 Bad Request）问题，增加了自动防御机制：

- **阈值限制**：
  - 源文件最大数量：**80**
  - 目标文件最大数量：**150**
- **自动截断**：超过阈值时，自动截断列表并打印警告日志，确保 AI 请求能成功发出。
- **降级策略**：如果源文件过多，系统会在日志中提示，建议用户分批处理。

```python
# 截断逻辑示例
MAX_SOURCE_FILES = 80
truncated_source = source_software[:MAX_SOURCE_FILES]
```

### 4. 代码清理：抑制废弃警告
**文件**: `src/software_organizer/ai_engines.py`

修复了启动时 `google.generativeai` 打印的 `FutureWarning`。

- 在导入模块前添加了 `warnings.filterwarnings`。
- 保证了控制台日志的清洁，不影响功能使用。

```python
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import google.generativeai as genai
# ...
```

---

## 其他更新

- **文档更新**：更新了 `CHANGELOG.md` 和 `README.md`（修正端口号为 8001）。
- **新增功能**：完整集成了"目标文件查重"功能，支持一键扫描清理重复软件。
