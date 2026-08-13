const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const document = {
    addEventListener() {},
    createElement(tagName) {
        const element = {
            tagName: tagName.toUpperCase(),
            className: '',
            textContent: '',
            value: '',
            selected: false,
            children: [],
            replaceChildren(...children) { this.children = children; },
        };
        return element;
    },
    querySelector() { return null; },
};

const context = {
    window: {},
    document,
    navigator: { language: 'en-US' },
    console,
    setTimeout() {},
    clearTimeout() {},
    setInterval() {},
    clearInterval() {},
    fetch: async () => ({ ok: true, json: async () => ({}) }),
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/app.js', 'utf8'), context);

const hostile = '"><img src=x onerror=alert(1)>';
const select = { value: '', children: [], replaceChildren(...children) { this.children = children; } };
context.replaceSelectOptions(select, [hostile]);
assert.equal(select.children[0].value, hostile);
assert.equal(select.children[0].textContent, hostile);

const classes = new Set(['file-row', 'target', 'delete-candidate']);
const hint = { textContent: '将替换/删除', title: '' };
const row = {
    dataset: { path: '' },
    classList: {
        contains(value) { return classes.has(value); },
        toggle(value, enabled) { enabled ? classes.add(value) : classes.delete(value); },
    },
    querySelector(selector) {
        if (selector === 'input[type="checkbox"]') return checkbox;
        if (selector === '.file-decision-hint') return hint;
        return null;
    },
};
const checkbox = { checked: false, closest() { return row; } };
const specialPath = '/tmp/Tool "]\\.dmg';
row.dataset.path = specialPath;
const card = {
    querySelectorAll(selector) {
        assert.equal(selector, '.file-row');
        return [
            { dataset: { path: '/tmp/other.dmg' }, querySelector() { return null; } },
            row,
        ];
    },
};
document.querySelector = selector => {
    assert.equal(selector, '.group-card[data-group="3"]');
    return card;
};
assert.equal(context.findFileCheckbox(3, specialPath), checkbox);
context.syncFileSelectionUI(3, specialPath, true);
assert.equal(checkbox.checked, true);
assert.equal(classes.has('delete-candidate'), false);
assert.equal(hint.textContent, '保留');

const notification = { children: [], replaceChildren(...children) { this.children = children; } };
context.setIconText(notification, 'fa-info-circle', hostile);
assert.equal(notification.children[1].textContent, hostile);

console.log('Frontend safety checks passed.');
