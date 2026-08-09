/* Lightweight local UI language adaptation. No network translation is used. */
(function () {
    const translations = {
        '文件入库扫描': 'Scan Inbox',
        '生成清理计划': 'Build Cleanup Plan',
        '批量入库整理': 'Organize Files',
        '执行清理计划': 'Run Cleanup Plan',
        '总数': 'Total',
        '源目录': 'Source',
        '目标目录': 'Target',
        '配置路径': 'Configured Paths',
        '分组': 'Groups',
        '整理模式': 'Organize Mode',
        '清理模式': 'Cleanup Mode',
        '点击 "文件入库扫描" 开始智能分组': 'Click "Scan Inbox" to start grouping',
        '正在扫描重复文件...': 'Scanning for duplicate files...',
        '等待入库分析': 'Waiting for an inbox scan',
        '点击顶部 "文件入库扫描" 按钮，将源目录文件与目标目录智能匹配分组': 'Click "Scan Inbox" above to match source files with the target library',
        '系统设置': 'System Settings',
        '通用设置': 'General',
        '文件格式': 'File Formats',
        '清理策略': 'Cleanup Policy',
        'AI 模型': 'AI Models',
        '源目录 (扫描目录)': 'Source folder',
        '浏览': 'Browse',
        '文件分类管理': 'File Category Management',
        '新增分类': 'Add Category',
        '历史版本保留': 'Version Retention',
        '默认保留最近版本数': 'Default versions to keep',
        '用于没有单独策略的文件分组。填 0 表示不自动勾选最近版本。': 'Used for groups without a specific policy. Use 0 to avoid automatic keep selections.',
        '排除清理关键词': 'Protected cleanup keywords',
        '文件名或分组名称包含这些关键词时，会在清理计划中受保护。': 'Files or groups containing these keywords are protected from cleanup.',
        '排除清理目录': 'Protected cleanup folders',
        '位于这些目录下的文件不会进入批量清理队列。': 'Files under these folders are excluded from batch cleanup.',
        '未配置': 'Not configured',
        '已配置': 'Configured',
        '验证连接': 'Test Connection',
        '保存': 'Save',
        '保存设置': 'Save Settings',
        '配置 / 修改': 'Configure / Edit',
        'Ollama (本地)': 'Ollama (Local)',
        '请先验证连接': 'Test the connection first',
        '操作历史': 'Operation History',
        '选择目录': 'Choose Folder',
        '上级': 'Parent',
        '取消': 'Cancel',
        '选择当前目录': 'Choose This Folder',
        '新增文件分类': 'Add File Category',
        '分类 ID (英文小写，无空格)': 'Category ID (lowercase English, no spaces)',
        '分类名称': 'Category name',
        '文件格式 (逗号分隔)': 'File formats (comma-separated)',
        '确定': 'Confirm',
        '使用说明': 'Help',
        '请确认': 'Please Confirm',
        '开启/关闭 AI 智能分析': 'Toggle AI assistance',
        '选择 AI 模型': 'Choose an AI model',
        '未检查': 'Not checked',
        '关闭设置': 'Close settings',
        '打开设置': 'Open settings',
        '刷新': 'Refresh',
        '刷新文件列表': 'Refresh file list',
        '历史': 'History',
        '查看操作历史': 'View operation history',
        '帮助': 'Help',
        '打开使用说明': 'Open help',
        '关闭操作历史': 'Close operation history',
        '关闭目录选择': 'Close folder chooser',
        '关闭新增分类': 'Close add category dialog',
        '关闭使用说明': 'Close help',
        '关闭确认窗口': 'Close confirmation dialog',
        'AI 分析中...': 'AI analysis...',
        '规则匹配中...': 'Matching with local rules...',
        '分析中...': 'Analyzing...',
        '测试中...': 'Testing...',
        '连接成功！': 'Connection successful!',
        '空目录': 'Empty folder',
        '暂无操作记录': 'No operation history',
        '删除': 'Delete',
        '跳过': 'Skip',
        '保留': 'Keep',
        '入库转移': 'Inbox transfers',
        '旧版清理': 'Old versions to clean',
        '受保护跳过': 'Protected skips',
        '未选目标': 'No target selected',
        '待清理文件预览': 'Cleanup preview',
        '未选择目标目录，将跳过转移': 'No target folder; transfers will be skipped',
        '受保护版本，不会删除': 'Protected versions will not be deleted',
        '覆盖同名文件': 'Overwrite existing files',
        '执行': 'Run',
        '有匹配': 'Matched',
        '目标目录': 'Target folder',
        '源目录': 'Source folder',
        '默认规则': 'Default rule',
        '还原': 'Restore',
        '删除分类': 'Delete category',
        '保留2版': 'Keep 2 versions',
        '永不清理': 'Never clean up',
        '取消此分组的保留策略': 'Cancel this group retention policy',
        '移除此组 (不影响文件)': 'Remove this group (files are unchanged)',
        '选择目标...': 'Choose target...',
        '未配置目录': 'No folder configured',
        '未识别版本，显示文件修改日期': 'No version found; showing modified date',
        '此文件受保留策略保护': 'Protected by retention policy',
        '配置目录': 'Configure folders',
        '配置 AI 模型': 'Configure an AI model',
        '审核分组': 'Review groups',
        '执行处理': 'Run the operation',
        '核心功能说明': 'Core Features',
        '跨格式查重': 'Cross-format matching',
        '保留策略': 'Retention policy',
        '手动保留规则': 'Manual keep rules',
        '默认策略': 'Default policy',
        '全局策略': 'Global policy',
        'AI 建议': 'AI suggestion',
        '转移失败保护': 'Transfer failure protection',
        '自定义分类': 'Custom categories',
        'AI 模型状态指示灯': 'AI model status indicators',
        '本地配置与安全': 'Local configuration and security',
        '配置位置': 'Configuration location',
        '密钥处理': 'Key handling',
        '文件权限': 'File permissions',
        '依赖方式': 'Dependency model',
        '批量入库整理说明': 'Batch organization',
        '转移操作': 'Transfer operation',
        '清理操作': 'Cleanup operation',
        '安全确认': 'Confirmation',
        '安全边界': 'Safety boundaries',
        '变体保护': 'Variant protection',
        '小技巧': 'Tips',
        '加载配置失败': 'Configuration load failed',
        '设置已保存': 'Settings saved',
        '保存失败': 'Save failed',
        '清理策略已重新加载': 'Cleanup policy reloaded',
        '加载清理策略失败': 'Failed to load cleanup policy',
        '清理策略已保存': 'Cleanup policy saved',
        '保存清理策略失败': 'Failed to save cleanup policy',
        '目标目录已更新': 'Target folder updated',
        '格式已更新': 'Formats updated',
        '格式冲突': 'Format conflict',
        '请输入分类 ID': 'Enter a category ID',
        '请输入分类名称': 'Enter a category name',
        '请输入文件格式': 'Enter file formats',
        '分类 ID 只能包含小写字母和数字': 'Category ID can only contain lowercase letters and numbers',
        '分析正在进行中...': 'Analysis is already running...',
        '源目录没有可分析的文件': 'No supported files found in the source folder',
        '已使用本地规则继续': '; continuing with local rules',
        '分析失败': 'Analysis failed',
        '分析完成': 'Analysis complete',
        '清理计划已生成': 'Cleanup plan generated',
        '清理分析失败': 'Cleanup analysis failed',
        'AI 分析完成': 'AI analysis complete',
        '已加载': 'Loaded',
        '条 AI 建议': ' AI recommendations',
        'AI 建议保留': 'Keep per AI suggestion',
        '分类已删除': 'Category deleted',
        '分类已创建': 'Category created',
        '已还原': 'Restored',
        '无法识别分组名称': 'Unable to identify the group name',
        '保存保留策略失败': 'Failed to save retention policy',
        '取消保留策略失败': 'Failed to cancel retention policy',
        '处理完成': 'Processing complete',
        '转移完成': 'Transfer complete',
        '成功': ' succeeded',
        '失败': ' failed',
        '已存在跳过': ' existing, skipped',
        '删除': 'Delete',
        '连接失败': 'Connection failed',
        '加载失败': 'Load failed',
        '正在连接': 'Connecting',
        '系统工具': 'system tools',
        '签名包': 'signed packages',
        '归档资料': 'archived documents',
        '文档资料': 'Documents',
        'Mac 应用': 'Mac apps',
        'iOS 应用': 'iOS apps',
        'Windows 应用': 'Windows apps',
        '：': ': '
    };

    const requestedLocale = new URLSearchParams(window.location.search).get('locale');
    const systemLocale = requestedLocale || navigator.language || navigator.userLanguage || 'en-US';
    const isChinese = /^zh(?:[-_]|$)/i.test(systemLocale);
    const locale = isChinese ? 'zh-CN' : systemLocale;
    const pairs = Object.entries(translations).sort((a, b) => b[0].length - a[0].length);

    function translate(value) {
        if (isChinese || typeof value !== 'string') return value;
        return pairs.reduce((text, [source, target]) => text.replaceAll(source, target), value);
    }

    function translateRoot(root) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);
        textNodes.forEach(node => {
            if (!node.parentElement || ['SCRIPT', 'STYLE'].includes(node.parentElement.tagName)) return;
            const translated = translate(node.nodeValue);
            if (translated !== node.nodeValue) node.nodeValue = translated;
        });

        root.querySelectorAll?.('[title], [aria-label], [placeholder], [data-tooltip]').forEach(element => {
            ['title', 'aria-label', 'placeholder', 'data-tooltip'].forEach(attribute => {
                if (element.hasAttribute(attribute)) {
                    const current = element.getAttribute(attribute);
                    const translated = translate(current);
                    if (translated !== current) element.setAttribute(attribute, translated);
                }
            });
        });
    }

    function initialize() {
        document.documentElement.lang = locale;
        if (isChinese) return;
        translateRoot(document.body);
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.type === 'characterData') translateRoot(mutation.target.parentElement || document.body);
                if (mutation.type === 'childList') mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) translateRoot(node);
                });
                if (mutation.type === 'attributes') {
                    const current = mutation.target.getAttribute(mutation.attributeName);
                    const translated = translate(current);
                    if (translated !== current) mutation.target.setAttribute(mutation.attributeName, translated);
                }
            });
        });
        observer.observe(document.body, {
            subtree: true,
            childList: true,
            characterData: true,
            attributes: true,
            attributeFilter: ['title', 'aria-label', 'placeholder', 'data-tooltip']
        });
    }

    window.FileOrganizerI18n = { locale, isChinese, translate };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }
})();
