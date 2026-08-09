/**
 * File Organizer Pro - 主应用入口
 * 
 * 核心流程：
 * 1. 页面加载 - 显示源目录软件列表
 * 2. AI 文件分析 - 去目标目录找相同软件，合并分组
 * 3. 批量处理 - 转移保留的源文件，删除未保留的
 */

// ==============================================================================
// 全局状态
// ==============================================================================

const state = {
    config: {},
    categories: {},          // 文件分类配置
    sourceSoftware: [],      // 源目录软件
    targetSoftware: [],      // 目标目录软件（AI 分析后填充）
    analysisGroups: [],      // AI 分析后的分组
    directories: {},         // 各分类的目标子目录列表
    currentEngine: 'gemini',
    selectedToKeep: new Set(),
    isAnalyzing: false,
    isAnalyzed: false,       // 是否已执行 AI 分析
    dirPickerTarget: null,
    currentDirPath: '/',
    mode: 'organize',        // 'organize' | 'deduplicate'
    useAI: false,            // AI 默认关闭，配置加载后恢复用户选择
    aiRecommendationsCache: {}, // AI 推荐缓存 {groupHash: recommendation}
    retentionRules: null
};

// ==============================================================================
// 初始化
// ==============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    await loadDirectories();
    await loadRetentionRules();
    await loadAIRecommendationsCache(); // 加载持久化的 AI 建议

    // 初始化 toggle 状态
    const toggleBtn = document.getElementById('ai-toggle-btn');
    if (toggleBtn) {
        // 绑定点击事件
        toggleBtn.addEventListener('click', toggleAIMode);
        updateToggleState(); // 根据配置决定是否可用
    }

    bindEvents();

    // 自动加载源目录软件列表
    if (state.config.source_dir) {
        await loadSourceSoftware();
    }
});

/**
 * 从后端加载已持久化的 AI 建议缓存
 */
async function loadAIRecommendationsCache() {
    try {
        const result = await apiCall('/ai-recommendations', 'GET');
        if (result && result.recommendations) {
            state.aiRecommendationsCache = result.recommendations;
            console.log(`已加载 ${Object.keys(result.recommendations).length} 条 AI 建议缓存`);
        }
    } catch (error) {
        console.error('加载 AI 建议缓存失败:', error);
    }
}

// ==============================================================================
// API 调用
// ==============================================================================


async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(`/api${endpoint}`, options);

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '请求失败');
    }

    return response.json();
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function formatFileMtime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(Number(timestamp) * 1000);
    if (Number.isNaN(date.getTime())) return '';
    const locale = window.FileOrganizerI18n?.locale || navigator.language || 'en-US';
    return date.toLocaleDateString(locale, { year: '2-digit', month: '2-digit', day: '2-digit' });
}

function isAIProviderReady(provider, config = null) {
    const providerConfig = config || state.config[provider] || {};

    if (!provider) return false;
    if (provider === 'gemini' || provider === 'deepseek') {
        return Boolean(
            providerConfig.configured ||
            providerConfig.api_key ||
            providerConfig.api_key_masked
        );
    }
    if (provider === 'ollama') {
        return Boolean(providerConfig.url || providerConfig.configured);
    }

    return Boolean(
        providerConfig.configured ||
        providerConfig.api_key ||
        providerConfig.api_key_masked ||
        providerConfig.url
    );
}

// ==============================================================================
// 配置管理
// ==============================================================================

async function loadConfig() {
    try {
        state.config = await apiCall('/config');
        state.categories = state.config.categories || {};

        // 恢复保存的引擎设置
        if (state.config.current_engine) {
            state.currentEngine = state.config.current_engine;
            const engineLabels = {
                'gemini': 'Gemini',
                'deepseek': 'DeepSeek',
                'ollama': 'Ollama'
            };
            const labelText = engineLabels[state.currentEngine] || state.currentEngine;
            const labelEl = document.getElementById('current-engine-label');
            const selectEl = document.getElementById('engine-select');
            if (labelEl) labelEl.textContent = labelText;
            if (selectEl) selectEl.value = state.currentEngine;
        }

        updateConfigUI();
        renderCategorySettings();

        // 加载保存的 AI Toggle 状态
        if (typeof state.config.use_ai !== 'undefined') {
            state.useAI = state.config.use_ai;
        }

        // 检查 AI 状态 (仅更新状态灯，不再自动禁用开关)
        await checkAIStatus();
        updateToggleState();
    } catch (error) {
        showNotification('加载配置失败: ' + error.message, 'error');
    }
}

async function saveSettings() {
    try {
        // 保存源目录
        const config = {
            source_dir: document.getElementById('cfg-source').value
        };

        await apiCall('/config', 'POST', config);
        state.config = { ...state.config, ...config };

        const cleanupTabActive = document.getElementById('tab-cleanup')?.classList.contains('active');
        if (cleanupTabActive) {
            const retentionSaved = await saveRetentionRules(false);
            if (!retentionSaved) return;
        }

        showNotification('设置已保存', 'success');
        closeModal('settings-modal');
        await loadDirectories();
        await loadSourceSoftware();
    } catch (error) {
        showNotification('保存失败: ' + error.message, 'error');
    }
}

function updateConfigUI() {
    document.getElementById('cfg-source').value = state.config.source_dir || '';

    updateModelStatus('gemini', state.config.gemini);
    updateModelStatus('deepseek', state.config.deepseek);
    updateModelStatus('ollama', state.config.ollama);

    // 更新已配置路径统计
    const configuredCount = Object.values(state.categories || {}).filter(c => c.target_dir).length;
    const configStatEl = document.getElementById('stat-configs');
    if (configStatEl) {
        configStatEl.textContent = configuredCount;
    }
}

async function toggleAIMode() {
    const btn = document.getElementById('ai-toggle-btn');
    // 不再检查 disabled 类，因为我们不再自动禁用它
    if (!btn) return;

    // 切换状态
    state.useAI = !state.useAI;

    // 更新 UI
    updateToggleState();

    // 保存状态到后端
    try {
        await apiCall('/config', 'POST', { use_ai: state.useAI });
    } catch (e) {
        console.error('保存 AI 开关状态失败', e);
    }
}

function updateToggleState() {
    const btn = document.getElementById('ai-toggle-btn');
    if (!btn) return;

    // 仅根据 state.useAI 更新 UI，不再强制禁用
    if (state.useAI) {
        btn.classList.add('active');
        btn.title = "已开启 AI 智能辅助";
    } else {
        btn.classList.remove('active');
        btn.title = "已关闭 AI (如需 AI 智能辅助请开启)";
    }

    // 同时也移除 disabled 类，确保始终可用
    btn.classList.remove('disabled');
}

// 渲染分类设置（目标目录和文件格式）
function renderCategorySettings() {
    const targetDirsContainer = document.getElementById('category-target-dirs');
    const formatsContainer = document.getElementById('category-formats-list');

    if (!targetDirsContainer || !formatsContainer) return;

    // 渲染目标目录设置
    let targetDirsHTML = '';
    // 将分类排序：general 排在最前（虽然 general 不显示目录，但保持一致性好），其他按名称
    const sortedCats = Object.entries(state.categories).sort((a, b) => {
        if (a[0] === 'general') return -1;
        if (b[0] === 'general') return 1;
        return a[1].name.localeCompare(b[1].name);
    });

    for (const [catId, cat] of sortedCats) {
        // 通用分类不需要配置目标目录
        if (catId === 'general') continue;

        const safeCatName = escapeHtml(cat.name || catId);
        const safeTargetDir = escapeHtml(cat.target_dir || '');

        targetDirsHTML += `
            <div class="form-group">
                <label>${safeCatName} 目标目录</label>
                <div class="input-group">
                    <input type="text" id="cfg-target-${catId}" 
                           value="${safeTargetDir}"
                           placeholder="选择 ${safeCatName} 文件存放目录"
                           onchange="updateCategoryTargetDir('${catId}')">
                    <button type="button" class="btn-secondary"
                        onclick="openDirPicker('category-target-${catId}')">浏览</button>
                </div>
            </div>
        `;
    }
    targetDirsContainer.innerHTML = targetDirsHTML;

    // 渲染文件格式设置
    let formatsHTML = '';
    for (const [catId, cat] of sortedCats) {
        let actionsHTML = '';
        const safeCatName = escapeHtml(cat.name || catId);
        let nameHTML = `<span class="category-name" title="${safeCatName}">${safeCatName}</span>`;

        if (catId === 'general') {
            // 通用分类：显示还原按钮，没有删除按钮
            actionsHTML = `
                <button type="button" class="btn-secondary btn-sm" onclick="restoreCategoryDefaults('${catId}')" title="还原默认设置">
                    <i class="fa-solid fa-rotate-left"></i> 还原
                </button>
            `;
            // 标识为默认规则
            nameHTML += `<span class="badge-default">默认规则</span>`;
        } else {
            // 普通分类：显示删除按钮
            actionsHTML = `
                <button type="button" class="btn-danger btn-sm" onclick="deleteCategory('${catId}', event)" title="删除分类">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
        }

        // 跨格式匹配开关
        const isCrossFormat = cat.cross_format_match || false;
        const toggleClass = isCrossFormat ? 'text-success' : 'text-secondary';
        const toggleIcon = isCrossFormat ? 'fa-toggle-on' : 'fa-toggle-off';
        const toggleTitle = isCrossFormat ? '已开启跨格式查重 (忽略扩展名差异)' : '跨格式查重已关闭 (仅匹配相同扩展名)';

        // 插入到操作按钮之前
        const toggleBtn = `
            <button type="button" class="btn-text btn-sm ${toggleClass}" 
                onclick="toggleCategoryCrossMatch('${catId}', event)" 
                style="margin-right: 8px;"
                title="${toggleTitle}">
                <i class="fa-solid ${toggleIcon} fa-lg"></i>
            </button>
        `;

        actionsHTML = toggleBtn + actionsHTML;

        formatsHTML += `
            <div class="category-item" id="category-item-${catId}">
                <div class="category-info">
                    ${nameHTML}
                    <span class="category-id">(${catId})</span>
                </div>
                <div class="category-formats">
                    <input type="text" id="cfg-formats-${catId}" 
                           value="${escapeHtml((cat.formats || []).join(','))}"
                           placeholder="例如: .dmg,.pkg"
                           onchange="updateCategoryFormats('${catId}')">
                </div>
                <div class="category-actions">
                    ${actionsHTML}
                </div>
            </div>
        `;
    }
    formatsContainer.innerHTML = formatsHTML;
}

async function loadRetentionRules(showToast = false) {
    try {
        const rules = await apiCall('/retention-rules');
        state.retentionRules = {
            global_keep_latest: 1,
            protected_keywords: [],
            protected_directories: [],
            software_policies: {},
            ...rules
        };
        renderRetentionSettings();
        if (showToast) showNotification('清理策略已重新加载', 'success');
    } catch (error) {
        showNotification('加载清理策略失败: ' + error.message, 'error');
    }
}

function renderRetentionSettings() {
    if (!state.retentionRules) return;

    const keepLatestInput = document.getElementById('retention-global-keep-latest');
    const keywordInput = document.getElementById('retention-protected-keywords');
    const directoryInput = document.getElementById('retention-protected-directories');

    if (keepLatestInput) {
        keepLatestInput.value = Number.isFinite(Number(state.retentionRules.global_keep_latest))
            ? String(state.retentionRules.global_keep_latest)
            : '1';
    }
    if (keywordInput) {
        keywordInput.value = (state.retentionRules.protected_keywords || []).join('\n');
    }
    if (directoryInput) {
        directoryInput.value = (state.retentionRules.protected_directories || []).join('\n');
    }
}

function parseRetentionList(value) {
    return String(value || '')
        .split(/[\n,]/)
        .map(item => item.trim())
        .filter(Boolean);
}

async function saveRetentionRules(showToast = true) {
    const keepLatestInput = document.getElementById('retention-global-keep-latest');
    const keywordInput = document.getElementById('retention-protected-keywords');
    const directoryInput = document.getElementById('retention-protected-directories');

    const keepLatest = Math.max(0, parseInt(keepLatestInput?.value || '1', 10) || 0);
    const payload = {
        global_keep_latest: keepLatest,
        protected_keywords: parseRetentionList(keywordInput?.value),
        protected_directories: parseRetentionList(directoryInput?.value)
    };

    try {
        const result = await apiCall('/retention-rules', 'PUT', payload);
        state.retentionRules = result.rules || { ...state.retentionRules, ...payload };
        renderRetentionSettings();
        const suffix = state.mode === 'deduplicate' ? '，重新生成清理计划后生效' : '';
        if (showToast) showNotification(`清理策略已保存${suffix}`, 'success');
        return true;
    } catch (error) {
        showNotification('保存清理策略失败: ' + error.message, 'error');
        return false;
    }
}

function updateModelStatus(provider, config) {
    const statusEl = document.getElementById(`status-${provider}`);
    const statusDot = document.getElementById(`status-dot-${provider}`);
    const dropdownDot = document.getElementById(`dropdown-dot-${provider}`);

    const isConfigured = isAIProviderReady(provider, config);

    if (statusEl) {
        if (isConfigured) {
            statusEl.textContent = '已配置';
            statusEl.classList.add('configured', 'active');
        } else {
            statusEl.textContent = '未配置';
            statusEl.classList.remove('configured', 'active');
        }
    }

    // 设置状态指示灯初始状态（灰色表示未验证）
    // 只有在验证连接后才会变成绿色/红色
    if (statusDot && !statusDot.classList.contains('success') && !statusDot.classList.contains('error')) {
        // 保持默认灰色状态
    }

    // 如果是初始加载，同步默认选中模型的状态
    if (provider === state.currentEngine) {
        const currentStatusDot = document.getElementById('current-engine-status');
        if (currentStatusDot && dropdownDot) {
            currentStatusDot.className = dropdownDot.className.replace('dropdown-status-dot', '').trim();
        }
    }
}

/**
 * 检查所有 AI 提供商的连接状态
 * 调用后端 /api/ai-status 端点，更新所有状态指示灯
 */
async function checkAIStatus() {
    try {
        const status = await apiCall('/ai-status');

        ['gemini', 'deepseek', 'ollama'].forEach(provider => {
            const providerStatus = status[provider];
            if (!providerStatus) return;

            const statusDot = document.getElementById(`status-dot-${provider}`);
            const dropdownDot = document.getElementById(`dropdown-dot-${provider}`);
            const statusBadge = document.getElementById(`status-${provider}`);

            // 更新状态徽章
            if (statusBadge) {
                if (providerStatus.configured) {
                    statusBadge.textContent = providerStatus.connected
                        ? (providerStatus.verified === false ? '已配置' : '已连接')
                        : '连接失败';
                    statusBadge.classList.toggle('active', providerStatus.connected);
                    statusBadge.classList.add('configured');
                } else {
                    statusBadge.textContent = '未配置';
                    statusBadge.classList.remove('configured', 'active');
                }
            }

            // 更新状态指示灯
            const dotClass = providerStatus.connected ? 'success' :
                (providerStatus.configured ? 'error' : '');
            const dotTitle = providerStatus.connected
                ? (providerStatus.verified === false ? '已配置，未实时验证' : '连接正常')
                : (providerStatus.error || (providerStatus.configured ? '连接失败' : '未配置'));

            if (statusDot) {
                statusDot.className = `status-dot ${dotClass}`;
                statusDot.title = dotTitle;
            }

            if (dropdownDot) {
                dropdownDot.className = `dropdown-status-dot status-dot ${dotClass}`;
                dropdownDot.title = dotTitle;
            }

            // 如果当前选中的是这个模型，更新按钮旁的状态指示灯
            if (provider === state.currentEngine) {
                const currentStatusDot = document.getElementById('current-engine-status');
                if (currentStatusDot) {
                    currentStatusDot.className = `status-dot ${dotClass}`;
                    currentStatusDot.title = dotTitle;
                }
            }

            if (providerStatus.models && providerStatus.models.length > 0) {
                const modelSelect = document.getElementById(`cfg-${provider}-model`);
                if (modelSelect && modelSelect.tagName === 'SELECT') {
                    const currentValue = modelSelect.value;
                    const hasValidSelection = currentValue && providerStatus.models.includes(currentValue);
                    modelSelect.innerHTML = providerStatus.models.map((m, index) =>
                        `<option value="${m}" ${(hasValidSelection && m === currentValue) || (!hasValidSelection && index === 0) ? 'selected' : ''}>${m}</option>`
                    ).join('');
                }
            }
        });

    } catch (error) {
        console.error('检查 AI 状态失败:', error);
    }
}

// 状态轮询定时器（仅轮询当前选中的引擎）
let statusPollingInterval = null;

function startStatusPolling() {
    if (statusPollingInterval) clearInterval(statusPollingInterval);

    // 每30秒只检查当前选中的引擎状态
    statusPollingInterval = setInterval(() => {
        // 如果页面不可见，跳过检查
        if (document.hidden) return;
        checkSelectedEngineStatus();
    }, 30000);
}

// 只检查当前选中引擎的状态
async function checkSelectedEngineStatus() {
    if (!state.currentEngine) return;

    try {
        const status = await apiCall('/ai-status');
        const providerStatus = status[state.currentEngine];
        if (!providerStatus) return;

        // 更新当前选中引擎的状态指示点
        const currentStatusDot = document.getElementById('current-engine-status');
        if (currentStatusDot) {
            const dotClass = providerStatus.connected ? 'success' :
                (providerStatus.configured ? 'error' : '');
            const dotTitle = providerStatus.connected
                ? (providerStatus.verified === false ? '已配置，未实时验证' : '连接正常')
                : (providerStatus.error || (providerStatus.configured ? '连接失败' : '未配置'));
            currentStatusDot.className = `status-dot ${dotClass}`;
            currentStatusDot.title = dotTitle;
        }
    } catch (error) {
        console.error('检查选中引擎状态失败:', error);
    }
}

// ==============================================================================
// 目录加载
// ==============================================================================

async function loadDirectories() {
    try {
        // 加载所有分类的目录
        for (const catId of Object.keys(state.categories)) {
            try {
                const data = await apiCall(`/directories/${catId}`);
                state.directories[catId] = data.directories || [];
            } catch (e) {
                state.directories[catId] = [];
            }
        }
    } catch (error) {
        console.error('加载目录失败:', error);
    }
}

function getDirectoryOptions(categoryId) {
    const dirs = state.directories[categoryId] || [];
    return '<option value="">选择目标...</option>' +
        dirs.map(dir => `
            <option value="${dir.path}">${dir.rel_path || dir.name}</option>
        `).join('');
}

// ==============================================================================
// 分类管理
// ==============================================================================

async function updateCategoryTargetDir(catId) {
    const input = document.getElementById(`cfg-target-${catId}`);
    if (!input) return;

    try {
        await apiCall(`/categories/${catId}`, 'PUT', {
            cat_id: catId,
            target_dir: input.value
        });
        state.categories[catId].target_dir = input.value;
        updateConfigUI(); // 刷新统计
        showNotification(`${state.categories[catId].name} 目标目录已更新`, 'success');
        await loadDirectories();
    } catch (error) {
        showNotification('更新失败: ' + error.message, 'error');
    }
}

async function updateCategoryFormats(catId) {
    const input = document.getElementById(`cfg-formats-${catId}`);
    if (!input) return;

    const formats = input.value.split(',').map(f => f.trim()).filter(f => f);

    try {
        await apiCall(`/categories/${catId}`, 'PUT', {
            cat_id: catId,
            formats: formats
        });
        state.categories[catId].formats = formats;
        showNotification(`${state.categories[catId].name} 格式已更新`, 'success');
    } catch (error) {
        showNotification('格式冲突: ' + error.message, 'error');
        // 恢复原值
        input.value = (state.categories[catId].formats || []).join(',');
    }
}

async function toggleCategoryCrossMatch(catId, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const cat = state.categories[catId];
    if (!cat) return;

    const newValue = !cat.cross_format_match;

    // 乐观更新 UI
    cat.cross_format_match = newValue;
    renderCategorySettings();

    try {
        await apiCall(`/categories/${catId}`, 'PUT', {
            cat_id: catId,
            cross_format_match: newValue
        });
        showNotification(`${cat.name} 跨格式查重配置已保存`, 'success');
    } catch (error) {
        showNotification('更新失败: ' + error.message, 'error');
        // 回滚
        cat.cross_format_match = !newValue;
        renderCategorySettings();
    }
}

function showConfirmation({ title = '请确认', message, confirmText = '确定', danger = false }) {
    return new Promise(resolve => {
        const modal = document.getElementById('confirmation-modal');
        const titleEl = document.getElementById('confirmation-title');
        const messageEl = document.getElementById('confirmation-message');
        const confirmBtn = document.getElementById('confirmation-confirm');
        const cancelBtn = document.getElementById('confirmation-cancel');
        const closeBtn = document.getElementById('confirmation-close');
        const previousFocus = document.activeElement;

        titleEl.textContent = title;
        messageEl.textContent = message;
        confirmBtn.textContent = confirmText;
        confirmBtn.classList.toggle('btn-danger', danger);
        confirmBtn.classList.toggle('btn-primary', !danger);

        const cleanup = result => {
            modal.classList.add('hidden');
            confirmBtn.removeEventListener('click', onConfirm);
            cancelBtn.removeEventListener('click', onCancel);
            closeBtn.removeEventListener('click', onCancel);
            modal.removeEventListener('click', onBackdrop);
            document.removeEventListener('keydown', onKeydown);
            previousFocus?.focus();
            resolve(result);
        };
        const onConfirm = () => cleanup(true);
        const onCancel = () => cleanup(false);
        const onBackdrop = event => {
            if (event.target === modal) cleanup(false);
        };
        const onKeydown = event => {
            if (event.key === 'Escape') cleanup(false);
        };

        confirmBtn.addEventListener('click', onConfirm);
        cancelBtn.addEventListener('click', onCancel);
        closeBtn.addEventListener('click', onCancel);
        modal.addEventListener('click', onBackdrop);
        document.addEventListener('keydown', onKeydown);
        modal.classList.remove('hidden');
        cancelBtn.focus();
    });
}

async function deleteCategory(catId, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const catName = state.categories[catId]?.name || catId;

    const confirmed = await showConfirmation({
        title: '删除文件分类',
        message: `确定要删除分类 "${catName}" 吗？此操作不会删除目录中的文件。`,
        confirmText: '删除分类',
        danger: true
    });
    if (!confirmed) return;

    try {
        await apiCall(`/categories/${catId}`, 'DELETE');
        delete state.categories[catId];
        renderCategorySettings();
        showNotification(`分类 "${catName}" 已删除`, 'success');
    } catch (error) {
        showNotification('删除失败: ' + error.message, 'error');
    }
}


function closeAddCategoryModal() {
    document.getElementById('add-category-modal').classList.add('hidden');
    // 清空输入
    document.getElementById('new-cat-id').value = '';
    document.getElementById('new-cat-name').value = '';
    document.getElementById('new-cat-formats').value = '';
}

function addNewCategory(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    // 打开模态框
    document.getElementById('add-category-modal').classList.remove('hidden');
    document.getElementById('new-cat-id').focus();
}

async function confirmAddCategory() {
    const catIdInput = document.getElementById('new-cat-id');
    const catNameInput = document.getElementById('new-cat-name');
    const catFormatsInput = document.getElementById('new-cat-formats');

    const catId = catIdInput.value.trim();
    if (!catId) {
        showNotification('请输入分类 ID', 'error');
        catIdInput.focus();
        return;
    }

    // 简单的 ID 验证 (仅限小写字母和数字)
    if (!/^[a-z0-9]+$/.test(catId)) {
        showNotification('分类 ID 只能包含小写字母和数字', 'error');
        catIdInput.focus();
        return;
    }

    const catName = catNameInput.value.trim();
    if (!catName) {
        showNotification('请输入分类名称', 'error');
        catNameInput.focus();
        return;
    }

    const formatsStr = catFormatsInput.value.trim();
    if (!formatsStr) {
        showNotification('请输入文件格式', 'error');
        catFormatsInput.focus();
        return;
    }

    const formatList = formatsStr.split(',').map(f => f.trim()).filter(f => f);
    // 确保格式以 . 开头
    const validFormats = formatList.map(f => f.startsWith('.') ? f : '.' + f);

    try {
        await apiCall('/categories', 'POST', {
            cat_id: catId,
            name: catName,
            formats: validFormats
        });
        state.categories[catId] = { name: catName, formats: validFormats, target_dir: '' };
        renderCategorySettings();
        showNotification(`分类 "${catName}" 已创建`, 'success');
        closeAddCategoryModal();
    } catch (error) {
        showNotification('创建失败: ' + error.message, 'error');
    }
}

async function restoreCategoryDefaults(catId) {
    const confirmed = await showConfirmation({
        title: '还原默认分类',
        message: `确定要将分类 "${catId}" 的名称、格式和匹配设置还原为默认值吗？`,
        confirmText: '还原默认值'
    });
    if (!confirmed) return;

    try {
        await apiCall(`/categories/${catId}/restore`, 'POST');
        // reload config to get defaults
        await loadConfig();
        showNotification(`分类 "${catId}" 已还原`, 'success');
    } catch (error) {
        showNotification('还原失败: ' + error.message, 'error');
    }
}


// ==============================================================================
// 加载源目录软件（默认显示）
// ==============================================================================

async function loadSourceSoftware() {
    const loadingEl = document.getElementById('loading-state');
    const emptyEl = document.getElementById('empty-state');
    const listEl = document.getElementById('groups-list');
    const hintEl = document.getElementById('analyze-hint');

    loadingEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');
    listEl.classList.add('hidden');

    // 重置模式和按钮文字 (退出查重模式)
    state.mode = 'organize';
    updateModeIndicator(); // 更新模式指示器
    const processBtnSpan = document.querySelector('#process-btn span');
    if (processBtnSpan) processBtnSpan.textContent = '批量入库整理';

    try {
        const data = await apiCall('/software');

        // 按当前平台过滤
        // state.sourceSoftware = data.software.filter(s => s.platform === state.currentPlatform);
        // 改为：显示所有扫描到的软件
        state.sourceSoftware = data.software;
        state.targetSoftware = [];
        state.isAnalyzed = false;
        state.deletedGroups = new Set(); // Reset deleted groups on reload

        // 更新统计
        updateStats();

        // 将源文件转为分组格式显示（每个文件单独一组）
        state.analysisGroups = state.sourceSoftware.map(software => ({
            software_name: software.name || software.filename,
            files: [{ ...software, location: 'source' }],
            suggested_path: ''
        }));

        // 默认全选
        state.selectedToKeep.clear();
        state.analysisGroups.forEach((group, index) => {
            // 每个初始分组只有一个源文件
            const file = group.files[0];
            if (file) {
                state.selectedToKeep.add(`${index}|${file.path}`);
            }
        });

        if (state.analysisGroups.length > 0) {
            hintEl.classList.remove('hidden');
            renderGroups();
        } else {
            emptyEl.classList.remove('hidden');
            hintEl.classList.add('hidden');
        }

    } catch (error) {
        showNotification('加载失败: ' + error.message, 'error');
        emptyEl.classList.remove('hidden');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function updateStats() {
    const totalCount = state.sourceSoftware.length + state.targetSoftware.length;
    document.getElementById('stat-total').textContent = totalCount;
    document.getElementById('stat-source').textContent = state.sourceSoftware.length;
    document.getElementById('stat-target').textContent = state.targetSoftware.length;

    // Count active groups (total - deleted)
    const deletedCount = state.deletedGroups ? state.deletedGroups.size : 0;
    const activeGroups = Math.max(0, state.analysisGroups.length - deletedCount);
    document.getElementById('stat-groups').textContent = activeGroups;

    // 更新批量按钮文字
    const processBtnSpan = document.querySelector('#process-btn span');
    if (processBtnSpan) {
        processBtnSpan.textContent = state.mode === 'deduplicate' ? '执行清理计划' : '批量入库整理';
    }

    // 更新批量处理按钮状态
    const processBtn = document.getElementById('process-btn');
    if (processBtn) {
        // 用户需求变更：不再因无数据而禁用按钮
        processBtn.classList.remove('btn-disabled');
        processBtn.classList.remove('disabled');
    }
}

// 更新模式指示器
function updateModeIndicator() {
    const indicator = document.getElementById('mode-indicator');
    const label = document.getElementById('mode-label');

    if (!indicator || !label) return;

    const modeConfig = {
        'organize': { show: false, text: '常规模式', icon: 'fa-folder' },
        'analyze': { show: true, text: '入库模式', icon: 'fa-inbox' },
        'deduplicate': { show: true, text: '清理计划', icon: 'fa-broom' }
    };

    const config = modeConfig[state.mode] || modeConfig['organize'];

    if (config.show) {
        indicator.style.display = 'inline-flex';

        // 构建显示文本：模式名 + AI 标签（如果启用）
        let displayText = config.text;
        if (state.useAI) {
            displayText += ' · AI';
        }
        label.textContent = displayText;

        // 更新图标
        const icon = indicator.querySelector('i');
        if (icon) {
            icon.className = `fa-solid ${config.icon}`;
        }
    } else {
        indicator.style.display = 'none';
    }
}

// ==============================================================================
// 核心：文件入库扫描 (原 AI 文件分析)
// ==============================================================================

async function inputManagement() {
    if (state.isAnalyzing) {
        showNotification('分析正在进行中...', 'warning');
        return;
    }

    if (state.sourceSoftware.length === 0) {
        showNotification('源目录没有可分析的文件', 'warning');
        return;
    }

    state.isAnalyzing = true;
    state.mode = 'analyze';
    updateModeIndicator(); // 更新模式指示器

    const loadingEl = document.getElementById('loading-state');
    const listEl = document.getElementById('groups-list');
    const hintEl = document.getElementById('analyze-hint');

    loadingEl.classList.remove('hidden');
    listEl.classList.add('hidden');
    hintEl.classList.add('hidden');

    const btn = document.getElementById('analyze-btn');
    const originalContent = '<i class="fa-solid fa-inbox"></i> <span>文件入库扫描</span>';

    let effectiveUseAI = state.useAI;

    // 根据是否使用 AI 显示不同文本
    if (!state.useAI) {
        // 非 AI 模式时的轻量引导
        showNotification('提示：开启右上角 AI 开关可获得更精准的智能分组建议', 'info');
    }

    if (effectiveUseAI && !isAIProviderReady(state.currentEngine)) {
        showNotification(`AI 引擎 (${state.currentEngine}) 未配置，已使用本地规则继续`, 'warning');
        effectiveUseAI = false;
    }

    if (effectiveUseAI) {
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles fa-spin"></i> <span>AI 分析中...</span>';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-filter fa-bounce"></i> <span>规则匹配中...</span>';
    }

    try {
        // 调用 分析 API (aiAnalyze 改名)
        const result = await apiCall('/analyze', 'POST', {
            engine: state.currentEngine,
            use_ai: effectiveUseAI // AI 未配置时自动降级为本地规则
        });

        state.analysisGroups = result.groups || [];
        state.targetSoftware = result.target_software || [];
        state.isAnalyzed = true;

        // 更新统计
        updateStats();

        // 默认勾选策略：
        // 1. 源文件：全部勾选
        // 2. 目标文件：仅勾选在 keep_rules 中的文件
        state.selectedToKeep.clear();

        state.analysisGroups.forEach((group, groupIndex) => {
            group.files?.forEach(file => {
                const key = `${groupIndex}|${file.path}`;
                const hasBackendRecommendation = typeof file.recommended_keep === 'boolean';

                if (file.is_kept || (hasBackendRecommendation && file.recommended_keep)) {
                    state.selectedToKeep.add(key);
                    return;
                }

                if (file.location === 'source' && !hasBackendRecommendation) {
                    // 源文件默认勾选
                    // 但对于 Universal 格式产生的多个分组，我们需要特殊的默认策略：
                    // 如果一个源文件出现在多个组中，只勾选第一个？还是全部？
                    // 如果全部勾选，根据互斥逻辑，最后被处理的那个会生效，前面的会被取消？
                    // 现在的 toggleFileKeep 逻辑是 "选中当前的，取消其他的"。
                    // 如果我们在这里依次 add，实际上不会触发 toggleFileKeep 的逻辑（因为我们直接操作 Set）。
                    // 所以我们需要手动处理互斥。
                    // 策略：如果是 Universal 文件（出现在多个组），只在第一个遇到的组中勾选。

                    // 检查该文件路径是否已经被选中过（意味着在之前的组中已经处理过）
                    // 我们需要遍历 selectedToKeep 来检查 path 是否已存在（效率较低但数据量不大）
                    let alreadySelected = false;
                    for (const existingKey of state.selectedToKeep) {
                        if (existingKey.endsWith(`|${file.path}`)) {
                            alreadySelected = true;
                            break;
                        }
                    }

                    if (!alreadySelected) {
                        state.selectedToKeep.add(key);
                    }
                }
            });
        });

        renderGroups();

        const matchedGroups = state.analysisGroups.filter(g => g.files.length > 1).length;
        const methodText = effectiveUseAI ? 'AI 分析' : '规则匹配';
        showNotification(`${methodText}完成！找到 ${matchedGroups} 个匹配组`, 'success');

    } catch (error) {
        showNotification('分析失败: ' + error.message, 'error');
    } finally {
        state.isAnalyzing = false;
        loadingEl.classList.add('hidden');
        btn.innerHTML = originalContent;
    }
}

// ==============================================================================
// 生成目标目录清理计划
// ==============================================================================

function computeDuplicateGroupCacheKey(group) {
    const fileSignature = (group.files || [])
        .map(file => [
            file.path || '',
            file.filename || '',
            file.version || '',
            file.size || 0,
            Math.round(file.mtime || 0)
        ].join('|'))
        .sort()
        .join(';');

    return `${group.software_name || ''}:${fileSignature}`;
}

async function deduplicateFiles() {
    if (state.isAnalyzing) return;

    // 切换模式
    state.mode = 'deduplicate';
    updateModeIndicator(); // 更新模式指示器
    state.isAnalyzing = true;

    // UI 状态更新
    const loadingEl = document.getElementById('loading-state');
    const listEl = document.getElementById('groups-list');
    const emptyEl = document.getElementById('empty-state');
    const hintEl = document.getElementById('analyze-hint');

    loadingEl.classList.remove('hidden');
    listEl.classList.add('hidden');
    emptyEl.classList.add('hidden');
    hintEl.classList.add('hidden');

    // 按钮状态
    const btn = document.getElementById('dedupe-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>分析中...</span>';

    try {
        const result = await apiCall('/analyze/duplicates', 'POST');

        // 立即隐藏 Loading，防止后续逻辑阻塞 UI
        loadingEl.classList.add('hidden');
        listEl.classList.remove('hidden');
        if (state.analysisGroups && state.analysisGroups.length === 0) {
            emptyEl.classList.remove('hidden');
        }

        state.analysisGroups = result.groups || [];
        state.sourceSoftware = []; // 查重模式下清空源
        state.targetSoftware = []; // 显示用，这里不重要
        state.deletedGroups = new Set(); // Reset deleted groups for deduplication

        // 更新统计 (只显示清理计划分组)
        document.getElementById('stat-groups').textContent = state.analysisGroups.length;

        // 自动勾选保留规则：
        // 1. 硬保护策略永远勾选。
        // 2. 手动保留规则优先。
        // 3. 否则使用后端生成的保留计划（默认最近版本/软件策略）。
        state.selectedToKeep.clear();
        state.analysisGroups.forEach((group, groupIndex) => {
            if (group.files && group.files.length > 0) {
                group.files.forEach(f => {
                    const shouldKeep = f.retention_protected || f.is_kept ||
                        (f.recommended_keep && f.manual_keep !== false);
                    if (shouldKeep) {
                        state.selectedToKeep.add(`${groupIndex}|${f.path}`);
                    }
                });

                if (!group.files.some(f => state.selectedToKeep.has(`${groupIndex}|${f.path}`))) {
                    state.selectedToKeep.add(`${groupIndex}|${group.files[0].path}`);
                }
            }
        });

        renderGroups();

        // 更新清理按钮状态
        updateCleanupButtonState();

        // 更新操作按钮文字
        const processBtnSpan = document.querySelector('#process-btn span');
        if (processBtnSpan) processBtnSpan.textContent = '执行清理计划';

        showNotification(`清理计划已生成：${result.count} 组疑似重复`, 'success');

        // ======================================================================
        // Phase 6: AI 增强 (先显示列表，后台分析)
        // 逻辑：
        // 1. 始终加载并应用已缓存的 AI 建议 (不管 AI 开关)
        // 2. 如果 AI 开启 且 有新的/变化的分组，后台调用 AI 分析
        // 3. 分析完成后更新 UI
        // ======================================================================
        (async () => {
            try {
                const groupHashMap = {}; // {groupIndex: hash}
                const groupsToAnalyze = []; // 需要 AI 分析的分组

                state.analysisGroups.forEach((group, index) => {
                    const hash = computeDuplicateGroupCacheKey(group);
                    groupHashMap[index] = hash;

                    // 如果缓存中没有，且 AI 开启，则加入待分析列表
                    if (!state.aiRecommendationsCache[hash] && state.useAI) {
                        groupsToAnalyze.push({ ...group, _originalIndex: index });
                    }
                });

                // === 2. 先应用所有已缓存的 AI 建议 (立即渲染) ===
                applyAIRecommendationsToUI(groupHashMap);

                // === 3. 如果有待分析的分组 且 AI 开启，后台分析 ===
                if (groupsToAnalyze.length > 0 && state.useAI) {
                    // 更新 UI 提示正在进行 AI 分析 (不阻塞)
                    const modeIndicator = document.querySelector('.mode-tag');
                    const originalModeText = modeIndicator?.textContent || '';
                    if (modeIndicator) {
                        modeIndicator.innerHTML = `${originalModeText} <span class="ai-analyzing-inline"><i class="fa-solid fa-spinner fa-spin"></i> 分析中(${groupsToAnalyze.length})</span>`;
                    }

                    const aiResult = await apiCall('/analyze/duplicates/ai', 'POST', {
                        groups: groupsToAnalyze
                    });

                    // 恢复模式标签
                    if (modeIndicator) modeIndicator.textContent = originalModeText;

                    // === 4. 将结果存入缓存 ===
                    const newRecommendations = {};
                    if (aiResult && aiResult.recommendations) {
                        aiResult.recommendations.forEach(rec => {
                            const originalGroup = groupsToAnalyze[rec.group_index];
                            if (originalGroup) {
                                const hash = groupHashMap[originalGroup._originalIndex];
                                state.aiRecommendationsCache[hash] = {
                                    ...rec,
                                    group_index: originalGroup._originalIndex
                                };
                                newRecommendations[hash] = {
                                    reason: rec.reason,
                                    keep_indices: rec.keep_indices
                                };
                            }
                        });
                    }

                    // 持久化保存
                    if (Object.keys(newRecommendations).length > 0) {
                        apiCall('/ai-recommendations', 'POST', {
                            recommendations: newRecommendations
                        }).catch(err => console.error('保存 AI 建议失败:', err));
                    }

                    // === 5. 应用新分析的建议到 UI ===
                    applyAIRecommendationsToUI(groupHashMap);

                    showNotification(`AI 分析完成 (新增 ${groupsToAnalyze.length} 组)`, 'success');
                } else if (Object.keys(state.aiRecommendationsCache).length > 0) {
                    // 有缓存但无新分析
                    const cachedCount = state.analysisGroups.filter((g, i) =>
                        state.aiRecommendationsCache[groupHashMap[i]]
                    ).length;
                    if (cachedCount > 0) {
                        showNotification(`已加载 ${cachedCount} 条 AI 建议`, 'info');
                    }
                }
            } catch (error) {
                console.error('AI Enrichment Error:', error);
            }
        })();

    } catch (error) {
        showNotification('查重分析失败: ' + error.message, 'error');
        state.mode = 'organize'; // 失败回退
        loadSourceSoftware();
    } finally {
        state.isAnalyzing = false;
        loadingEl.classList.add('hidden');
        btn.innerHTML = originalContent;
    }
}

// ==============================================================================
// AI 建议应用到 UI
// ==============================================================================

/**
 * 将 AI 建议应用到已渲染的分组卡片上
 * @param {Object} groupHashMap - {groupIndex: hash} 映射
 */
function applyAIRecommendationsToUI(groupHashMap) {
    state.analysisGroups.forEach((group, index) => {
        const hash = groupHashMap[index];
        const cachedRec = state.aiRecommendationsCache[hash];

        if (cachedRec) {
            if (state.mode === 'deduplicate' && Array.isArray(cachedRec.keep_indices)) {
                const hasManualOrProtected = group.files.some(f =>
                    f.has_keep_rule || f.retention_protected || typeof f.manual_keep === 'boolean'
                );

                // AI 只在没有手动/策略保护时接管默认勾选；保护项始终保留。
                if (!hasManualOrProtected) {
                    group.files.forEach((file, fileIndex) => {
                        const key = `${index}|${file.path}`;
                        const shouldKeep = cachedRec.keep_indices.includes(fileIndex);
                        if (shouldKeep || file.retention_protected) {
                            state.selectedToKeep.add(key);
                        } else {
                            state.selectedToKeep.delete(key);
                        }

                        const checkbox = document.querySelector(
                            `.group-card[data-group="${index}"] .file-row[data-path="${file.path}"] input[type="checkbox"]`
                        );
                        if (checkbox) checkbox.checked = state.selectedToKeep.has(key);
                    });
                }
            }

            const groupCard = document.querySelector(`.group-card[data-group="${index}"]`);
            if (groupCard && !groupCard.querySelector('.ai-recommendation-badge')) {
                // 1. 添加推荐徽章
                const header = groupCard.querySelector('.group-header');
                if (header) {
                    const badge = document.createElement('div');
                    badge.className = 'ai-recommendation-badge';
                    badge.innerHTML = `<i class="fa-solid fa-robot"></i> AI 建议`;
                    header.appendChild(badge);
                }

                // 2. 添加理由文本
                const fileList = groupCard.querySelector('.group-files');
                if (fileList && cachedRec.reason) {
                    const reasonDiv = document.createElement('div');
                    reasonDiv.className = 'ai-reason';
                    reasonDiv.textContent = `💡 ${cachedRec.reason}`;
                    groupCard.insertBefore(reasonDiv, fileList);
                }

                // 3. 高亮推荐文件
                if (cachedRec.keep_indices && cachedRec.keep_indices.length > 0) {
                    const fileItems = groupCard.querySelectorAll('.file-item, .file-row');
                    cachedRec.keep_indices.forEach(idx => {
                        if (fileItems[idx]) {
                            fileItems[idx].classList.add('ai-recommended');
                            const hint = fileItems[idx].querySelector('.file-decision-hint');
                            if (hint && !hint.textContent.includes('AI')) {
                                hint.textContent = 'AI 建议保留';
                            }
                        }
                    });
                }
            }
        }
    });
}

// ==============================================================================
// 渲染分组列表
// ==============================================================================

function renderGroups() {
    const emptyEl = document.getElementById('empty-state');
    const listEl = document.getElementById('groups-list');

    if (state.analysisGroups.length === 0) {
        emptyEl.classList.remove('hidden');
        listEl.classList.add('hidden');
        return;
    }

    emptyEl.classList.add('hidden');
    listEl.classList.remove('hidden');

    listEl.innerHTML = state.analysisGroups.map((group, groupIndex) => {
        // Skip deleted groups
        if (state.deletedGroups && state.deletedGroups.has(groupIndex)) return '';

        const hasTarget = group.files.some(f => f.location === 'target');
        const cardClass = hasTarget ? 'group-card has-match' : 'group-card';
        const isDuplicateGroup = state.mode === 'deduplicate' || group.is_duplicate_group;
        const retentionSummary = group.retention_summary || {};
        const protectedCount = retentionSummary.protected_count || 0;
        const deleteCandidateCount = retentionSummary.delete_candidate_count || 0;
        const safeGroupName = escapeHtml(group.software_name || '未命名分组');

        // 找到目标目录中已有软件的路径
        const existingTarget = group.files.find(f => f.location === 'target');
        const defaultTargetPath = existingTarget ? (existingTarget.parent_dir || '') : '';
        const safeDefaultTargetPath = escapeHtml(defaultTargetPath);

        const cleanupSummary = isDuplicateGroup ? `
            <div class="cleanup-summary">
                <span><i class="fa-solid fa-shield-halved"></i> 已保护 ${protectedCount} 个</span>
                <span><i class="fa-solid fa-broom"></i> 可清理 ${deleteCandidateCount} 个</span>
                ${retentionSummary.policy?.keep_latest ? `<span>策略：保留最近 ${escapeHtml(retentionSummary.policy.keep_latest)} 个版本</span>` : ''}
                ${retentionSummary.policy?.never_delete ? '<span>策略：此分组永不清理</span>' : ''}
            </div>
        ` : '';

        return `
        <div class="${cardClass}" data-group="${groupIndex}">
            <div class="group-header">
                <div class="group-title">
                    <input type="checkbox" class="group-checkbox"
                           onclick="toggleGroupAll(${groupIndex}, this.checked)">
                    <i class="fa-solid fa-cube"></i>
                    <span class="group-name" title="${safeGroupName}">${safeGroupName}</span>
                    <span class="group-count">${group.files?.length || 0} 个文件</span>
                    ${hasTarget ? '<span class="match-badge">有匹配</span>' : ''}
                </div>
                <div class="group-actions">
                    ${isDuplicateGroup ? `
                        <button class="btn-mini" onclick="setSoftwareRetention(${groupIndex}, 2)" title="以后此分组默认保留最近 2 个版本">
                            保留2版
                        </button>
                        <button class="btn-mini" onclick="setSoftwareRetention(${groupIndex}, null, true)" title="以后此分组所有版本都不自动清理">
                            永不清理
                        </button>
                        ${retentionSummary.policy && Object.keys(retentionSummary.policy).length > 0 ? `
                            <button class="btn-mini danger" onclick="resetSoftwareRetention(${groupIndex})" title="取消此分组的保留策略">
                                取消策略
                            </button>
                        ` : ''}
                    ` : ''}
                    <button class="btn-icon-only text-danger" onclick="deleteGroup(${groupIndex})" title="移除此组 (不影响文件)">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            ${cleanupSummary}
            <div class="group-files">
                ${(group.files || []).map((file, fileIndex) => {
            const isSource = file.location === 'source';
            const keepKey = `${groupIndex}|${file.path}`;
            const isSelected = state.selectedToKeep.has(keepKey);
            const isProtected = Boolean(file.retention_protected);
            const isDeleteCandidate = !isSource && !isSelected && !isProtected;
            const locationClass = isSource ? 'source' : 'target';
            const locationLabel = isSource ? '源目录' : '目标目录';
            const rowClass = [
                'file-row',
                locationClass,
                isProtected ? 'retention-protected' : '',
                isDeleteCandidate ? 'delete-candidate' : '',
                file.recommended_keep ? 'recommended-keep' : ''
            ].filter(Boolean).join(' ');
            const decisionHint = isProtected
                ? (file.retention_reason || '受保护')
                : isDeleteCandidate
                    ? '将替换/删除'
                    : isSelected
                        ? (file.recommend_reason || '保留')
                        : '';
            const safeFilename = escapeHtml(file.filename || '');
            const safeFilePath = escapeHtml(file.path || '');
            const safeDecisionHint = escapeHtml(decisionHint);
            const categoryId = file.category || 'mac';
            const categoryName = file.category_name || state.categories[categoryId]?.name || '未知';
            const safeCategoryName = escapeHtml(categoryName);
            const categoryClass = (categoryId || 'unknown').replace(/[^a-z0-9_-]/gi, '-');
            const safeVersion = escapeHtml(file.version || '');
            const safeModifiedDate = escapeHtml(formatFileMtime(file.mtime));
            const safeSize = escapeHtml(file.size_formatted || '-');
            // 智能下拉框逻辑：
            // 1. 优先显示匹配到的目录 (Top Priority)
            // 2. 显示一级子目录 (Level-1 Subdirectories)
            // 3. 总是包含根目录
            // 4. 自动选中建议的路径 (suggestedPath)

            let targetOptions = '';
            const addedPaths = new Set();

            // 获取建议路径 (优先使用文件特定的推荐路径，其次是组的推荐路径)
            const suggestedPath = file.recommended_path || group.suggested_path || '';
            const defaultTargetDir = state.categories[categoryId]?.target_dir || '';

            // 辅助函数：标准化路径 (移除末尾斜杠)
            const normalizePath = (p) => p && p.endsWith('/') ? p.slice(0, -1) : p;
            const normSuggested = normalizePath(suggestedPath);

            // 辅助函数：添加选项
            const addOption = (path, displayName, icon = '📂') => {
                if (!path || addedPaths.has(path)) return;

                const normPath = normalizePath(path);
                const isSelected = normPath === normSuggested ? 'selected' : '';

                targetOptions += `<option value="${escapeHtml(path)}" ${isSelected}>${icon} ${escapeHtml(displayName)}</option>`;
                addedPaths.add(path);
            };

            // 1. 添加匹配到的路径 (High Priority)
            // 从同组的目标文件中提取
            const targetFilesInGroup = group.files.filter(f => f.location === 'target');
            targetFilesInGroup.forEach(targetFile => {
                let targetDirPath = '';
                const parentDir = targetFile.parent_dir || '';

                if (parentDir && defaultTargetDir) {
                    targetDirPath = parentDir.startsWith('/') ? parentDir : `${defaultTargetDir}/${parentDir}`;
                } else if (defaultTargetDir) {
                    targetDirPath = defaultTargetDir;
                }

                if (targetDirPath) {
                    const displayPath = parentDir || '根目录 (匹配)';
                    addOption(targetDirPath, displayPath, '🎯');
                }
            });

            // 1.5 确保建议路径也被添加 (如果它不在匹配列表中)
            // 解决图2问题：如果没有名字，应该显示为根目录
            if (suggestedPath && !addedPaths.has(suggestedPath)) {
                // 计算相对路径用于显示
                let display = suggestedPath;
                if (defaultTargetDir && suggestedPath.startsWith(defaultTargetDir)) {
                    display = suggestedPath.substring(defaultTargetDir.length).replace(/^\//, '');
                }

                // 如果是根目录 (display为空)，显示明确名称
                if (!display) {
                    const catName = state.categories[categoryId]?.name || categoryId;
                    display = `${catName} (根目录)`;
                }

                addOption(suggestedPath, display, '✨');
            }

            // 2. 添加根目录 (放在一级目录之前，作为默认选项)
            if (defaultTargetDir) {
                const categoryName = state.categories[categoryId]?.name || categoryId;
                addOption(defaultTargetDir, `${categoryName} (根目录)`, '📁');
            }

            // 3. 添加一级子目录 (Level-1)，按名称排序
            const allDirectories = (state.directories[categoryId] || []).sort((a, b) => {
                const nameA = a.rel_path || a.name || '';
                const nameB = b.rel_path || b.name || '';
                return nameA.localeCompare(nameB);
            });

            allDirectories.forEach(dir => {
                // 仅显示一级子目录：rel_path 不包含分隔符
                const isLevel1 = dir.rel_path && !dir.rel_path.includes('/') && !dir.rel_path.includes('\\');

                if (isLevel1) {
                    addOption(dir.path, dir.rel_path);
                }
            });

            // 4. 如果没有选项，显示未配置
            if (!targetOptions) {
                targetOptions += `<option value="">未配置目录</option>`;
            }

            const existingPathLabel = file.parent_dir || '/';
            const safeExistingPathLabel = escapeHtml(existingPathLabel);
            const targetCol = isSource ? `
                        <div class="file-col-target">
                            <select class="inline-target-select" 
                                    id="file-target-${groupIndex}-${fileIndex}"
                                    data-path="${safeFilePath}">
                                ${targetOptions}
                            </select>
                        </div>
                    ` : `
                        <div class="file-col-target">
                            <span class="existing-path" title="${safeExistingPathLabel}">📁 ${safeExistingPathLabel}</span>
                        </div>
                    `;

            return `
                    <div class="${rowClass}" data-path="${safeFilePath}" data-default-target="${safeDefaultTargetPath}">
                        <div class="file-col-check">
                            <input type="checkbox" 
                                   ${isSelected ? 'checked' : ''}
                                   ${isProtected ? 'disabled' : ''}
                                   title="${isProtected ? escapeHtml(file.retention_reason || '此文件受保留策略保护') : ''}"
                                   data-path="${safeFilePath}"
                                   data-group="${groupIndex}"
                                   onchange="toggleFileKeep(this.dataset.path, this.checked, parseInt(this.dataset.group))">
                        </div>
                        <div class="file-col-name">
                            <i class="fa-solid ${isSource ? 'fa-arrow-right-to-bracket' : 'fa-folder-tree'}"></i>
                            <div class="file-name-stack">
                                <span class="filename" title="${safeFilename}">${safeFilename}</span>
                                <div class="file-badges">
                                    <span class="category-tag ${categoryClass}">${safeCategoryName}</span>
                                    ${decisionHint ? `<span class="file-decision-hint" title="${safeDecisionHint}">${safeDecisionHint}</span>` : ''}
                                </div>
                            </div>
                        </div>
                        <div class="file-col-location">
                            <span class="location-tag ${locationClass}">${locationLabel}</span>
                        </div>
                        <div class="file-col-size">${safeSize}</div>
                        <div class="file-col-version">
                            ${safeVersion
                    ? `<span class="version-tag" title="版本 ${safeVersion}">v${safeVersion}</span>`
                    : safeModifiedDate
                        ? `<span class="modified-date-tag" title="未识别版本，显示文件修改日期">${safeModifiedDate}</span>`
                        : '<span class="version-empty">-</span>'}
                        </div>
                        ${targetCol}
                    </div>
                `}).join('')}
            </div>
        </div>
    `}).join('');

    // 默认选中第一个选项（匹配目录优先，否则默认目录）
    state.analysisGroups.forEach((group, groupIndex) => {
        group.files.forEach((file, fileIndex) => {
            if (file.location === 'source') {
                const select = document.getElementById(`file-target-${groupIndex}-${fileIndex}`);
                if (select && select.options.length > 0) {
                    const hasSelectedOption = [...select.options].some(option => option.selected);
                    if (!hasSelectedOption) {
                        // 直接选中第一个选项（按构建顺序：匹配目录 > 默认目录）
                        select.selectedIndex = 0;
                    }
                }
            }

            // 处理 Keep 状态 (从后端获取) - 适用于源文件和目标文件
            if (file.retention_protected || file.is_kept || (file.recommended_keep && file.manual_keep !== false)) {
                const key = `${groupIndex}|${file.path}`;
                state.selectedToKeep.add(key);
                // 还要更新 checkbox UI
                const checkbox = document.querySelector(`.group-card[data-group="${groupIndex}"] .file-row[data-path="${file.path}"] input[type="checkbox"]`);
                if (checkbox) checkbox.checked = true;
            }
        });
    });
}

/**
 * ✅ 稳定方法 - 文件选择状态切换核心逻辑
 * 
 * 关键设计决策：
 * 1. 使用 Composite Key 格式: `${groupIndex}|${path}`
 * 2. 同步逻辑：同一文件在所有组中保持相同选中状态
 * 3. 调用 Keep Rule API 持久化选择
 * 
 * 修改前请确认影响范围！
 */
async function toggleFileKeep(path, checked, groupIndex) {
    const key = `${groupIndex}|${path}`;
    console.log(`[ToggleFileKeep] Group: ${groupIndex}, Path: "${path}", Key: "${key}", Checked: ${checked}`);

    // 同步逻辑：确保同一文件在所有组中的选中状态一致
    // 如果一个文件出现在多个组（例如通用文件被多个分类匹配），
    // 那么在一个组中选中它（Keep），应该在所有组中都选中它，防止被意外删除。
    // 反之亦然。

    // update current key first
    if (checked) {
        state.selectedToKeep.add(key);
    } else {
        state.selectedToKeep.delete(key);
    }

    // sync others
    state.analysisGroups.forEach((g, gIdx) => {
        if (gIdx !== groupIndex) {
            // 检查该组是否也有这个文件 (同一源文件可能出现在多个组)
            const hasFile = g.files.some(f => f.path === path);
            if (hasFile) {
                const otherKey = `${gIdx}|${path}`;
                if (checked) {
                    if (!state.selectedToKeep.has(otherKey)) {
                        state.selectedToKeep.add(otherKey);
                        // Update UI
                        const otherCheckbox = document.querySelector(`.group-card[data-group="${gIdx}"] .file-row[data-path="${path}"] input[type="checkbox"]`);
                        if (otherCheckbox) otherCheckbox.checked = true;
                    }
                } else {
                    if (state.selectedToKeep.has(otherKey)) {
                        state.selectedToKeep.delete(otherKey);
                        // Update UI
                        const otherCheckbox = document.querySelector(`.group-card[data-group="${gIdx}"] .file-row[data-path="${path}"] input[type="checkbox"]`);
                        if (otherCheckbox) otherCheckbox.checked = false;
                    }
                }
            }
        }
    });

    state.analysisGroups.forEach(group => {
        group.files?.forEach(file => {
            if (file.path === path) {
                file.manual_keep = checked;
                file.is_kept = checked;
            }
        });
    });

    // 查找对应的文件对象以获取软件名和文件名
    let softwareName = "";
    let filename = "";

    // 注意：只在当前组查找
    const group = state.analysisGroups[groupIndex];
    if (group) {
        const file = group.files.find(f => f.path === path);
        if (file) {
            softwareName = file.name;
            filename = file.filename;
        }
    }

    // 保存手动保留规则（优先使用文件名，因为包含版本信息且路径无关）
    try {
        await apiCall('/rules/keep', 'POST', {
            filename: filename, // 优先标识
            file_path: path,
            keep: checked,
            software_name: softwareName
        });
    } catch (e) {
        console.error("保存手动保留规则失败:", e);
    }

    // 更新清理按钮状态
    updateCleanupButtonState();
    renderGroups();
}

/**
 * 更新清理按钮状态
 * 
 * 在查重模式下，如果有任何未选中的文件（即将被删除），
 * 则启用"清理重复文件"按钮。
 */
function updateCleanupButtonState() {
    if (state.mode !== 'deduplicate') return;

    const processBtn = document.getElementById('process-btn');
    if (!processBtn) return;

    // 用户需求变更：不再禁用按钮，点击后由处理逻辑判断是否有选中文件
    // 始终启用按钮
    processBtn.disabled = false;
    processBtn.classList.remove('disabled');

    // 强制确保样式生效
    processBtn.style.opacity = '1';
    processBtn.style.cursor = 'pointer';
    processBtn.style.pointerEvents = 'auto';

    console.log('[ButtonState] Forced enabled per user request');
}

function toggleGroupAll(groupIndex, checked) {
    const group = state.analysisGroups[groupIndex];
    if (!group || !group.files) return;

    group.files.forEach(file => {
        if (!checked && file.retention_protected) return;
        const key = `${groupIndex}|${file.path}`;
        if (checked) {
            state.selectedToKeep.add(key);
        } else {
            state.selectedToKeep.delete(key);
        }
    });

    // 更新 UI
    const card = document.querySelector(`.group-card[data-group="${groupIndex}"]`);
    if (card) {
        card.querySelectorAll('.file-row input[type="checkbox"]').forEach(cb => {
            if (cb.disabled && !checked) return;
            cb.checked = checked;
        });
    }
}

function getGroupPolicyName(groupIndex) {
    const group = state.analysisGroups[groupIndex];
    if (!group) return '';

    const firstFileName = group.files?.[0]?.name;
    if (firstFileName) return firstFileName;

    return (group.software_name || '')
        .replace(/\s*\([^)]*\)\s*/g, ' ')
        .replace(/\s+-\s+.*$/, '')
        .trim();
}

async function setSoftwareRetention(groupIndex, keepLatest = null, neverDelete = false) {
    const softwareName = getGroupPolicyName(groupIndex);
    if (!softwareName) {
        showNotification('无法识别分组名称，未保存策略', 'error');
        return;
    }

    try {
        await apiCall('/retention/software', 'POST', {
            software_name: softwareName,
            keep_latest: keepLatest,
            never_delete: neverDelete
        });

        const message = neverDelete
            ? `已设置：${softwareName} 永不自动清理`
            : `已设置：${softwareName} 保留最近 ${keepLatest} 个版本`;
        showNotification(message, 'success');
        await deduplicateFiles();
    } catch (error) {
        showNotification('保存保留策略失败: ' + error.message, 'error');
    }
}

async function resetSoftwareRetention(groupIndex) {
    const softwareName = getGroupPolicyName(groupIndex);
    if (!softwareName) {
        showNotification('无法识别分组名称，未取消策略', 'error');
        return;
    }

    try {
        await apiCall('/retention/software', 'POST', {
            software_name: softwareName,
            reset: true
        });
        showNotification(`已取消 ${softwareName} 的保留策略`, 'success');
        await deduplicateFiles();
    } catch (error) {
        showNotification('取消保留策略失败: ' + error.message, 'error');
    }
}

/**
 * 移除分组 (仅从 UI 和处理列表中移除，不删除文件)
 */
function deleteGroup(groupIndex) {
    if (!state.deletedGroups) state.deletedGroups = new Set();

    // Add to deleted set
    state.deletedGroups.add(groupIndex);

    // Uncheck all files in this group to prevent batch processing
    toggleGroupAll(groupIndex, false);

    // Re-render UI
    renderGroups();
    updateStats();

    // Show feedback toast (optional)
    // showNotification('分组已移除', 'info'); 
}

// Make deleteGroup available globally for onclick handlers
window.deleteGroup = deleteGroup;

// ==============================================================================
// 批量处理
// ==============================================================================

function destinationPathForTransfer(item) {
    const destDir = (item.destination || '').replace(/\/+$/, '');
    return `${destDir}/${item.filename}`;
}

function buildBatchPlan() {
    const plan = {
        toTransfer: [],
        toDelete: [],
        noTarget: [],
        protectedSkipped: [],
        removedDeleteTargetCount: 0
    };
    const seenTransfers = new Set();

    state.analysisGroups.forEach((group, groupIndex) => {
        if (state.deletedGroups && state.deletedGroups.has(groupIndex)) return;

        group.files?.forEach((file, fileIndex) => {
            const isSelected = state.selectedToKeep.has(`${groupIndex}|${file.path}`);

            if (file.location === 'source') {
                if (!isSelected) return;

                const select = document.getElementById(`file-target-${groupIndex}-${fileIndex}`);
                const targetDir = select?.value;
                if (!targetDir) {
                    plan.noTarget.push(file.filename);
                    return;
                }

                if (!seenTransfers.has(file.path)) {
                    plan.toTransfer.push({
                        path: file.path,
                        destination: targetDir,
                        filename: file.filename
                    });
                    seenTransfers.add(file.path);
                }
                return;
            }

            if (file.location === 'target' || (!file.location && file.path)) {
                if (file.retention_protected) {
                    plan.protectedSkipped.push(file.filename);
                    state.selectedToKeep.add(`${groupIndex}|${file.path}`);
                    return;
                }

                if (!isSelected) {
                    plan.toDelete.push(file.path);
                }
            }
        });
    });

    const transferDestinations = new Set(plan.toTransfer.map(destinationPathForTransfer));
    const uniqueDeletePaths = [];
    const seenDeletePaths = new Set();
    const originalDeleteCount = plan.toDelete.length;

    plan.toDelete.forEach(path => {
        if (transferDestinations.has(path)) return;
        if (seenDeletePaths.has(path)) return;
        uniqueDeletePaths.push(path);
        seenDeletePaths.add(path);
    });

    plan.toDelete = uniqueDeletePaths;
    plan.removedDeleteTargetCount = originalDeleteCount - uniqueDeletePaths.length;
    return plan;
}

function ensureBatchReviewModal() {
    let modal = document.getElementById('batch-review-modal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'batch-review-modal';
    modal.className = 'modal hidden';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'batch-review-title');
    modal.innerHTML = `
        <div class="modal-content glass-panel batch-review-modal">
            <div class="modal-header">
                <h3 id="batch-review-title"><i class="fa-solid fa-list-check"></i> 确认处理计划</h3>
                <button id="batch-review-close" class="btn-close" aria-label="关闭处理计划"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="modal-body">
                <div id="batch-review-summary"></div>
            </div>
            <div class="modal-footer">
                <label class="batch-overwrite-toggle">
                    <input type="checkbox" id="batch-overwrite-existing">
                    <span>覆盖同名文件</span>
                </label>
                <div class="batch-review-actions">
                    <button id="batch-review-cancel" class="btn-secondary">取消</button>
                    <button id="batch-review-confirm" class="btn-primary">
                        <i class="fa-solid fa-play"></i> 执行
                    </button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    const modalContent = modal.querySelector('.modal-content');
    modalContent?.addEventListener('click', event => event.stopPropagation());
    return modal;
}

function renderBatchReviewSummary(plan) {
    const deletePreview = plan.toDelete.slice(0, 8).map(path => {
        const filename = path.split('/').pop() || path;
        return `
            <div class="batch-review-item delete" title="${escapeHtml(path)}">
                <i class="fa-solid fa-trash-can"></i>
                <span>${escapeHtml(filename)}</span>
                <em>删除</em>
            </div>
        `;
    }).join('');
    const noTargetPreview = plan.noTarget.slice(0, 6).map(name =>
        `<div class="batch-review-item warning">
            <i class="fa-solid fa-triangle-exclamation"></i>
            <span>${escapeHtml(name)}</span>
            <em>跳过</em>
        </div>`
    ).join('');
    const protectedPreview = plan.protectedSkipped.slice(0, 6).map(name =>
        `<div class="batch-review-item protected">
            <i class="fa-solid fa-shield-halved"></i>
            <span>${escapeHtml(name)}</span>
            <em>保留</em>
        </div>`
    ).join('');
    const extraDeleteCount = Math.max(0, plan.toDelete.length - 8);
    const extraNoTargetCount = Math.max(0, plan.noTarget.length - 6);
    const extraProtectedCount = Math.max(0, plan.protectedSkipped.length - 6);

    return `
        <div class="batch-review-grid">
            <div class="batch-review-stat"><strong>${plan.toTransfer.length}</strong><span>入库转移</span></div>
            <div class="batch-review-stat"><strong>${plan.toDelete.length}</strong><span>旧版清理</span></div>
            <div class="batch-review-stat"><strong>${plan.protectedSkipped.length}</strong><span>受保护跳过</span></div>
            <div class="batch-review-stat"><strong>${plan.noTarget.length}</strong><span>未选目标</span></div>
        </div>
        ${plan.removedDeleteTargetCount > 0 ? `
            <div class="batch-review-section">
                已自动移除 ${plan.removedDeleteTargetCount} 个转移目标路径的删除项，避免覆盖入库时误删新文件。
            </div>
        ` : ''}
        ${deletePreview ? `
            <div class="batch-review-section">
                <h4>待清理文件预览</h4>
                <div class="batch-review-list">${deletePreview}${extraDeleteCount ? `<div class="batch-review-more">还有 ${extraDeleteCount} 个未显示</div>` : ''}</div>
            </div>
        ` : ''}
        ${noTargetPreview ? `
            <div class="batch-review-section">
                <h4>未选择目标目录，将跳过转移</h4>
                <div class="batch-review-list">${noTargetPreview}${extraNoTargetCount ? `<div class="batch-review-more">还有 ${extraNoTargetCount} 个未显示</div>` : ''}</div>
            </div>
        ` : ''}
        ${protectedPreview ? `
            <div class="batch-review-section">
                <h4>受保护版本，不会删除</h4>
                <div class="batch-review-list">${protectedPreview}${extraProtectedCount ? `<div class="batch-review-more">还有 ${extraProtectedCount} 个未显示</div>` : ''}</div>
            </div>
        ` : ''}
    `;
}

function showBatchReviewDialog(plan) {
    return new Promise(resolve => {
        const modal = ensureBatchReviewModal();
        const summary = modal.querySelector('#batch-review-summary');
        const overwriteInput = modal.querySelector('#batch-overwrite-existing');
        const confirmBtn = modal.querySelector('#batch-review-confirm');
        const cancelBtn = modal.querySelector('#batch-review-cancel');
        const closeBtn = modal.querySelector('#batch-review-close');
        const previousFocus = document.activeElement;

        summary.innerHTML = renderBatchReviewSummary(plan);
        overwriteInput.checked = false;
        overwriteInput.disabled = plan.toTransfer.length === 0;
        overwriteInput.closest('.batch-overwrite-toggle')?.classList.toggle('disabled', plan.toTransfer.length === 0);

        const cleanup = (result) => {
            modal.classList.add('hidden');
            confirmBtn.removeEventListener('click', onConfirm);
            cancelBtn.removeEventListener('click', onCancel);
            closeBtn.removeEventListener('click', onCancel);
            modal.removeEventListener('click', onBackdrop);
            document.removeEventListener('keydown', onKeydown);
            previousFocus?.focus();
            resolve(result);
        };

        const onConfirm = () => cleanup({ overwrite: overwriteInput.checked });
        const onCancel = () => cleanup(null);
        const onBackdrop = event => {
            if (event.target === modal) cleanup(null);
        };
        const onKeydown = event => {
            if (event.key === 'Escape') cleanup(null);
        };

        confirmBtn.addEventListener('click', onConfirm);
        cancelBtn.addEventListener('click', onCancel);
        closeBtn.addEventListener('click', onCancel);
        modal.addEventListener('click', onBackdrop);
        document.addEventListener('keydown', onKeydown);
        modal.classList.remove('hidden');
        cancelBtn.focus();
    });
}

async function batchProcess() {
    if (state.analysisGroups.length === 0) {
        showNotification('没有可处理的文件', 'warning');
        return;
    }

    const plan = buildBatchPlan();

    if (plan.toTransfer.length === 0 && plan.toDelete.length === 0) {
        if (plan.noTarget.length > 0) {
            showNotification(`有 ${plan.noTarget.length} 个文件未选择目标目录，不会被转移`, 'warning');
        } else if (plan.protectedSkipped.length > 0) {
            showNotification(`没有需要处理的文件，${plan.protectedSkipped.length} 个受保护版本已跳过`, 'info');
        } else {
            showNotification('没有需要处理的文件', 'info');
        }
        return;
    }

    const confirmed = await showBatchReviewDialog(plan);
    if (!confirmed) return;

    const overwrite = confirmed.overwrite || false;

    let successTransfer = 0;
    let failedTransfer = [];
    let skippedExisting = [];

    for (const item of plan.toTransfer) {
        try {
            const result = await apiCall('/transfer', 'POST', {
                files: [item.path],
                destination: item.destination,
                overwrite: overwrite
            });

            // 检查返回结果
            if (result.success && result.success.length > 0) {
                successTransfer++;
            } else if (result.failed && result.failed.length > 0) {
                const failure = result.failed[0];
                if (!overwrite && failure.code === 'target_exists') {
                    skippedExisting.push(`${item.filename}: 目标目录已存在同名文件`);
                } else {
                    failedTransfer.push(`${item.filename}: ${failure.error}`);
                }
            } else {
                failedTransfer.push(`${item.filename}: 后端未返回明确的转移结果`);
            }
        } catch (e) {
            console.error(e);
            failedTransfer.push(`${item.filename}: ${e.message}`);
        }
    }

    let successDelete = 0;
    let failedDelete = [];
    let skippedDelete = 0;
    if (plan.toDelete.length > 0) {
        if (failedTransfer.length > 0 || skippedExisting.length > 0) {
            skippedDelete = plan.toDelete.length;
        } else {
            try {
                const result = await apiCall('/delete', 'POST', { files: plan.toDelete });
                successDelete = result.success?.length || 0;
                failedDelete = result.failed || [];
            } catch (e) {
                console.error(e);
                failedDelete = [{ error: e.message }];
            }
        }
    }

    // 显示结果
    const skippedDeleteText = skippedDelete > 0
        ? `；为保护已有文件，已跳过 ${skippedDelete} 个清理项`
        : '';
    if (failedTransfer.length > 0 || failedDelete.length > 0) {
        console.log('转移失败详情:', failedTransfer);
        const skippedText = skippedExisting.length > 0 ? `, ${skippedExisting.length} 已存在跳过` : '';
        const deleteFailedText = failedDelete.length > 0 ? `，删除 ${failedDelete.length} 失败` : '';
        const details = failedTransfer.slice(0, 3).join('\n') || failedDelete[0]?.error || '';
        showNotification(`处理完成: 转移 ${successTransfer} 成功${skippedText}, ${failedTransfer.length} 失败${deleteFailedText}${skippedDeleteText}${details ? `\n${details}` : ''}`, 'warning');
    } else if (skippedExisting.length > 0) {
        console.log('目标已存在，已跳过:', skippedExisting);
        showNotification(`转移完成: ${successTransfer} 成功, ${skippedExisting.length} 个目标已存在并跳过${skippedDeleteText}；如需替换，请在确认弹窗勾选“覆盖同名文件”`, 'warning');
    } else {
        showNotification(`处理完成！转移: ${successTransfer} | 删除: ${successDelete}`, 'success');
    }

    // 记录打钩的目标文件到 keep_rules（以便下次自动勾选）
    const keptTargetFiles = [];
    state.analysisGroups.forEach((group, groupIndex) => {
        group.files?.forEach(file => {
            if (file.location === 'target' && state.selectedToKeep.has(`${groupIndex}|${file.path}`)) {
                keptTargetFiles.push({
                    path: file.path,  // 文件路径
                    filename: file.filename, // 文件名（关键）
                    name: file.name   // 分组名称
                });
            }
        });
    });

    // 批量保存 keep_rules（使用文件名优先）
    for (const fileInfo of keptTargetFiles) {
        try {
            await apiCall('/rules/keep', 'POST', {
                filename: fileInfo.filename, // 优先标识
                file_path: fileInfo.path,
                keep: true,
                software_name: fileInfo.name
            });
        } catch (e) {
            console.error('保存 keep 规则失败:', e);
        }
    }

    await loadSourceSoftware();
}

// ==============================================================================

// ==============================================================================
// AI 连接测试
// ==============================================================================

async function testConnection(provider) {
    const resultEl = document.getElementById(`test-result-${provider}`);
    const statusDot = document.getElementById(`status-dot-${provider}`);

    resultEl.classList.remove('hidden');
    resultEl.className = 'test-result testing';
    resultEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 测试中...';

    // 更新状态指示灯为测试中（黄色）
    if (statusDot) {
        statusDot.className = 'status-dot warning';
        statusDot.title = '测试中...';
    }

    try {
        let testConfig = { provider };

        if (provider === 'gemini' || provider === 'deepseek') {
            testConfig.api_key = document.getElementById(`cfg-${provider}-key`).value;
            testConfig.model_name = document.getElementById(`cfg-${provider}-model`).value;
        } else if (provider === 'ollama') {
            testConfig.url = document.getElementById('cfg-ollama-url').value;
            testConfig.model_name = document.getElementById('cfg-ollama-model').value;
        }

        const response = await apiCall('/test-connection', 'POST', testConfig);

        resultEl.className = 'test-result success';
        resultEl.innerHTML = '<i class="fa-solid fa-check-circle"></i> 连接成功！';

        // 更新状态指示灯为成功（绿色）
        if (statusDot) {
            statusDot.className = 'status-dot success';
            statusDot.title = '连接正常';
        }

        // 同步下拉菜单中的状态指示灯
        const dropdownDot = document.getElementById(`dropdown-dot-${provider}`);
        if (dropdownDot) {
            dropdownDot.className = 'dropdown-status-dot status-dot success';
            dropdownDot.title = '连接正常';
        }

        // 如果当前选中的是这个模型，更新按钮旁的状态指示灯
        if (state.currentEngine === provider) {
            const currentStatusDot = document.getElementById('current-engine-status');
            if (currentStatusDot) {
                currentStatusDot.className = 'status-dot success';
                currentStatusDot.title = '连接正常';
            }
        }

        // 动态填充模型下拉列表
        if (response.models && response.models.length > 0) {
            const modelSelect = document.getElementById(`cfg-${provider}-model`);
            if (modelSelect && modelSelect.tagName === 'SELECT') {
                const currentValue = modelSelect.value;
                // 如果没有当前值或当前值不在新列表中，选中第一个
                const hasValidSelection = currentValue && response.models.includes(currentValue);
                modelSelect.innerHTML = response.models.map((m, index) =>
                    `<option value="${m}" ${(hasValidSelection && m === currentValue) || (!hasValidSelection && index === 0) ? 'selected' : ''}>${m}</option>`
                ).join('');
            }
        }

    } catch (error) {
        resultEl.className = 'test-result error';
        resultEl.innerHTML = `<i class="fa-solid fa-exclamation-circle"></i> ${error.message}`;

        // 更新状态指示灯为失败（红色）
        if (statusDot) {
            statusDot.className = 'status-dot error';
            statusDot.title = '连接失败';
        }

        // 同步下拉菜单中的状态指示灯
        const dropdownDot = document.getElementById(`dropdown-dot-${provider}`);
        if (dropdownDot) {
            dropdownDot.className = 'dropdown-status-dot status-dot error';
            dropdownDot.title = '连接失败';
        }

        // 如果当前选中的是这个模型，更新按钮旁的状态指示灯
        if (state.currentEngine === provider) {
            const currentStatusDot = document.getElementById('current-engine-status');
            if (currentStatusDot) {
                currentStatusDot.className = 'status-dot error';
                currentStatusDot.title = '连接失败';
            }
        }
    }
}

// ==============================================================================
// 目录选择器
// ==============================================================================

function openDirPicker(target) {
    state.dirPickerTarget = target;
    state.currentDirPath = '/';

    document.getElementById('dir-picker-modal').classList.remove('hidden');
    loadDirList(state.currentDirPath);
}

function closeDirPicker() {
    document.getElementById('dir-picker-modal').classList.add('hidden');
}

async function loadDirList(path) {
    const listEl = document.getElementById('dir-list');
    listEl.innerHTML = '<div class="loading-spinner"></div>';

    document.getElementById('current-dir-path').textContent = path;

    try {
        const data = await apiCall('/browse', 'POST', { path });
        state.currentDirPath = data.current;

        listEl.innerHTML = data.items.map(item => `
            <div class="dir-item" data-path="${escapeHtml(item.path)}" onclick="navigateToDir(this.dataset.path)">
                <i class="fa-solid fa-folder"></i>
                <span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
            </div>
        `).join('') || '<p class="empty-dir">空目录</p>';
    } catch (error) {
        listEl.innerHTML = `<p class="error">加载失败: ${escapeHtml(error.message)}</p>`;
    }
}

function navigateToDir(path) {
    loadDirList(path);
}

function goToParentDir() {
    const parentPath = state.currentDirPath.split('/').slice(0, -1).join('/') || '/';
    loadDirList(parentPath);
}

function selectCurrentDir() {
    // 处理固定目标
    const fixedTargets = {
        'source': 'cfg-source'
    };

    if (fixedTargets[state.dirPickerTarget]) {
        document.getElementById(fixedTargets[state.dirPickerTarget]).value = state.currentDirPath;
    } else if (state.dirPickerTarget?.startsWith('category-target-')) {
        // 处理动态分类目标: category-target-{catId}
        const catId = state.dirPickerTarget.replace('category-target-', '');
        const inputEl = document.getElementById(`cfg-target-${catId}`);
        if (inputEl) {
            inputEl.value = state.currentDirPath;
            // 自动触发更新
            updateCategoryTargetDir(catId);
        }
    }

    closeDirPicker();
}

// ==============================================================================
// 历史记录
// ==============================================================================

async function loadHistory() {
    const listEl = document.getElementById('history-list');
    listEl.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const data = await apiCall('/history');

        if (data.logs.length === 0) {
            listEl.innerHTML = '<p class="empty-history">暂无操作记录</p>';
            return;
        }

        listEl.innerHTML = data.logs.map(log => {
            const safeFilename = escapeHtml(log.filename || '');
            const safeDestination = escapeHtml(log.destination_path || '');
            const actionClass = log.action === 'transfer' ? 'transfer' : 'delete';
            const actionIcon = log.action === 'transfer' ? 'fa-arrow-right' : 'fa-trash';
            const meta = log.action === 'transfer' ? `转移至: ${safeDestination}` : '已删除';

            return `
            <div class="history-item">
                <div class="history-icon ${actionClass}">
                    <i class="fa-solid ${actionIcon}"></i>
                </div>
                <div class="history-info">
                    <div class="history-filename" title="${safeFilename}">${safeFilename}</div>
                    <div class="history-meta">
                        ${meta}
                    </div>
                    <div class="history-time">${new Date(log.timestamp).toLocaleString()}</div>
                </div>
            </div>
        `}).join('');
    } catch (error) {
        listEl.innerHTML = `<p class="error">加载失败: ${escapeHtml(error.message)}</p>`;
    }
}

// ==============================================================================
// AI 模型配置
// ==============================================================================

function toggleEdit(provider) {
    const editEl = document.getElementById(`edit-${provider}`);
    editEl.classList.toggle('hidden');

    const config = state.config[provider] || {};

    if (provider === 'gemini' || provider === 'deepseek') {
        const keyInput = document.getElementById(`cfg-${provider}-key`);
        keyInput.value = '';
        keyInput.placeholder = config.configured ? '已保存，留空保持不变' : '输入 API Key';
        const modelSelect = document.getElementById(`cfg-${provider}-model`);
        if (modelSelect && config.model_name) {
            if (![...modelSelect.options].some(option => option.value === config.model_name)) {
                modelSelect.add(new Option(config.model_name, config.model_name));
            }
            modelSelect.value = config.model_name;
        }
    } else if (provider === 'ollama') {
        document.getElementById('cfg-ollama-url').value = config.url || 'http://127.0.0.1:11434';
        document.getElementById('cfg-ollama-model').value = config.model_name || '';
    }
}

async function saveModelConfig(provider) {
    let config = {};

    if (provider === 'gemini' || provider === 'deepseek') {
        const apiKey = document.getElementById(`cfg-${provider}-key`).value.trim();
        config = {
            model_name: document.getElementById(`cfg-${provider}-model`).value
        };
        if (apiKey) {
            config.api_key = apiKey;
        }
    } else if (provider === 'ollama') {
        config = {
            url: document.getElementById('cfg-ollama-url').value,
            model_name: document.getElementById('cfg-ollama-model').value
        };
    }

    try {
        await apiCall('/config', 'POST', { [provider]: config });
        state.config[provider] = {
            ...(state.config[provider] || {}),
            ...config,
            configured: Boolean(config.api_key || state.config[provider]?.configured)
        };

        updateModelStatus(provider, state.config[provider]);
        showNotification(`${provider} 配置已保存`, 'success');

        document.getElementById(`edit-${provider}`).classList.add('hidden');
    } catch (error) {
        showNotification('保存失败: ' + error.message, 'error');
    }
}

// ==============================================================================
// 设置标签页切换
// ==============================================================================

function switchSettingsTab(tab, btnElement) {
    // 隐藏所有标签页内容
    document.querySelectorAll('#settings-modal .tab-content').forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('active');
    });

    // 移除所有标签按钮激活状态
    document.querySelectorAll('#settings-modal .tab-btn').forEach(el => {
        el.classList.remove('active');
    });

    // 显示对应的标签页内容
    const tabContent = document.getElementById(`tab-${tab}`);
    if (tabContent) {
        tabContent.classList.remove('hidden');
        tabContent.classList.add('active');
    }

    // 激活对应的标签按钮
    if (btnElement) {
        btnElement.classList.add('active');
    } else {
        // 如果没有传入按钮元素（如代码调用），尝试通过 ID 激活
        const btn = document.getElementById(`btn-tab-${tab}`);
        if (btn) btn.classList.add('active');
    }

    // 切换到 AI 模型标签页时检查状态
    if (tab === 'models') {
        checkAIStatus();
    } else if (tab === 'cleanup') {
        if (!state.retentionRules) {
            loadRetentionRules();
        } else {
            renderRetentionSettings();
        }
    }
}

function setupSettingsTabs() {
    ['general', 'formats', 'cleanup', 'models'].forEach(tabName => {
        const btn = document.getElementById(`btn-tab-${tabName}`);
        if (btn) {
            btn.addEventListener('click', () => {
                switchSettingsTab(tabName, btn);
            });
        }
    });
}

// ==============================================================================
// 模态框
// ==============================================================================

function openModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
}

// ==============================================================================
// 通知
// ==============================================================================

function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fa-solid ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
        <span>${message}</span>
    `;

    container.appendChild(notification);

    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ==============================================================================
// 事件绑定
// ==============================================================================

function bindEvents() {
    setupSettingsTabs(); // 初始化设置标签页事件

    // 打开设置模态框
    document.getElementById('settings-btn').addEventListener('click', () => {
        openModal('settings-modal');
        // 打开设置时检查 AI 状态
        checkAIStatus();
    });
    document.getElementById('close-settings').addEventListener('click', () => closeModal('settings-modal'));
    document.getElementById('history-btn').addEventListener('click', () => {
        openModal('history-modal');
        loadHistory();
    });
    document.getElementById('close-history').addEventListener('click', () => closeModal('history-modal'));

    // 帮助模态框
    document.getElementById('help-btn').addEventListener('click', () => openModal('help-modal'));
    document.getElementById('close-help').addEventListener('click', () => closeModal('help-modal'));

    document.getElementById('close-dir-picker').addEventListener('click', closeDirPicker);
    document.getElementById('close-add-category').addEventListener('click', closeAddCategoryModal);
    document.getElementById('refresh-btn').addEventListener('click', loadSourceSoftware);

    // AI 引擎选择
    const engineLabels = {
        'gemini': 'Gemini',
        'deepseek': 'DeepSeek',
        'ollama': 'Ollama'
    };

    document.querySelectorAll('#engine-dropdown-menu .dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            const value = item.dataset.value;
            state.currentEngine = value;

            // 使用映射表获取正确的显示名称
            const labelText = engineLabels[value] || value;
            document.getElementById('current-engine-label').textContent = labelText;
            document.getElementById('engine-select').value = value;
            document.getElementById('engine-dropdown-menu').classList.remove('show');

            // 同步更新按钮旁的状态指示灯
            const dropdownDot = document.getElementById(`dropdown-dot-${value}`);
            const currentStatusDot = document.getElementById('current-engine-status');
            if (dropdownDot && currentStatusDot) {
                currentStatusDot.className = dropdownDot.className.replace('dropdown-status-dot', '').trim();
                currentStatusDot.title = dropdownDot.title;
            }

            // 保存设置到后端
            apiCall('/config', 'POST', { current_engine: value }).catch(err => {
                console.error('保存引擎设置失败:', err);
            });

            // 立即检查新引擎状态
            checkAIStatus();
        });
    });

    // 下拉菜单打开时触发状态检查
    const dropdownBtn = document.getElementById('engine-dropdown-btn');
    if (dropdownBtn) {
        dropdownBtn.addEventListener('click', (e) => {
            // 如果菜单即将打开（当前没有显示），则触发检查
            const menu = document.getElementById('engine-dropdown-menu');
            if (menu && !menu.classList.contains('show')) {
                checkAIStatus(); // 打开下拉时检查所有引擎
            }
        });
    }

    // 页面加载2秒后自动检查一次所有引擎状态
    setTimeout(() => {
        checkAIStatus();
    }, 2000);

    // 启动选中引擎的状态轮询（30秒一次）
    startStatusPolling();

    document.getElementById('engine-dropdown-btn').addEventListener('click', () => {
        document.getElementById('engine-dropdown-menu').classList.toggle('show');
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('#engine-dropdown-container')) {
            document.getElementById('engine-dropdown-menu').classList.remove('show');
        }
    });

    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.add('hidden');
        });

        // 阻止模态框内容区域的点击事件冒泡，防止误关闭
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
    });
}

// 导出全局函数
window.deduplicateFiles = deduplicateFiles;
window.batchProcess = batchProcess;
window.toggleFileKeep = toggleFileKeep;
window.toggleGroupAll = toggleGroupAll;
window.setSoftwareRetention = setSoftwareRetention;
window.resetSoftwareRetention = resetSoftwareRetention;
window.openDirPicker = openDirPicker;
window.closeDirPicker = closeDirPicker;
window.navigateToDir = navigateToDir;
window.goToParentDir = goToParentDir;
window.selectCurrentDir = selectCurrentDir;
window.toggleEdit = toggleEdit;
window.saveModelConfig = saveModelConfig;
window.saveSettings = saveSettings;
window.saveRetentionRules = saveRetentionRules;
window.loadRetentionRules = loadRetentionRules;
window.switchSettingsTab = switchSettingsTab;
window.testConnection = testConnection;
window.checkAIStatus = checkAIStatus;
window.addNewCategory = addNewCategory;
window.deleteCategory = deleteCategory;
window.updateCategoryTargetDir = updateCategoryTargetDir;
window.updateCategoryFormats = updateCategoryFormats;
window.closeAddCategoryModal = closeAddCategoryModal;
window.confirmAddCategory = confirmAddCategory;
window.inputManagement = inputManagement;
window.toggleAIMode = toggleAIMode;
window.toggleCategoryCrossMatch = toggleCategoryCrossMatch;
window.restoreCategoryDefaults = restoreCategoryDefaults;
