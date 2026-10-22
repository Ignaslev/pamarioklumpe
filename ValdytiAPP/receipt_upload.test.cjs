// Isolated UI logic tests: no browser, database, network or paid API requests.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
    constructor(tag = 'div', className = '') {
        this.tag = tag; this.className = className; this.children = [];
        this.dataset = {}; this.textContent = ''; this.disabled = false;
    }
    append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
    replaceChildren() { this.children = []; }
    matches(selector) {
        return selector.startsWith('.') ? this.className.split(' ').includes(selector.slice(1)) : this.tag === selector;
    }
    closest(selector) {
        if (selector.split(',').some(s => this.matches(s.trim()))) return this;
        return this.parent?.closest(selector) || null;
    }
    querySelector(selector) {
        for (const child of this.children) {
            if (child.matches(selector)) return child;
            const match = child.querySelector(selector); if (match) return match;
        }
        return null;
    }
}

function response(status, overrides = {}) {
    return {ok: true, redirected: false, status: 200, json: async () => ({
        id: 12, status, label: status, message: '', date: '', attempt: 2,
        process_url: '/process/', status_url: '/status/', cancel_url: '/cancel/', review_url: '/review/', ...overrides})};
}

function setup(fetch, initialStatus = 'processing') {
    const root = new Element('tr');
    root.dataset = {status: initialStatus, statusUrl: '/status/'};
    const title = new Element('td');
    title.append(new Element('p', 'receipt-row-message'));
    const date = new Element('td', 'receipt-row-date');
    const status = new Element('td', 'receipt-row-status');
    const actions = new Element('td', 'receipt-row-actions');
    const link = new Element('a'); link.href = '/review/';
    const button = new Element('button', initialStatus === 'processing' ? 'receipt-cancel' : 'receipt-retry');
    button.dataset = {url: initialStatus === 'processing' ? '/cancel/' : '/process/',
        statusUrl: '/status/', cancelUrl: '/cancel/', attempt: '1'};
    actions.append(link, button); root.append(title, date, status, actions);
    const events = {}, intervals = [], form = new Element('form');
    form.querySelector = () => ({value: 'test-csrf'});
    form.addEventListener = (name, callback) => { events[`form:${name}`] = callback; };
    const elements = {'receipt-upload-form': form, 'receipt-images': {files: []},
        'receipt-submit': new Element('button'), 'receipt-progress': new Element(), 'receipt-queue': new Element()};
    const document = {
        getElementById: id => elements[id], createElement: tag => new Element(tag),
        querySelectorAll: () => initialStatus === 'processing' ? [root] : [],
        addEventListener: (name, callback) => { events[name] = callback; },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/ValdytiAPP/js/receipt_upload.js'), 'utf8'), {
        document, fetch, AbortController, URLSearchParams, FormData: class {append() {}},
        setTimeout: () => 1, clearTimeout() {}, setInterval: callback => intervals.push(callback),
        window: {addEventListener() {}},
    });
    return {root, status, actions, events, intervals, button};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('automatic status checks recover a stale row without calling the paid process endpoint', async () => {
    const calls = [];
    const ui = setup(async (url, options) => { calls.push({url, options}); return response('failed', {message: 'Expired'}); });
    ui.intervals[0](); await flush();
    assert.equal(ui.status.textContent, 'failed');
    assert.ok(ui.actions.querySelector('.receipt-retry'));
    assert.equal(ui.actions.querySelector('.receipt-cancel'), null);
    ui.intervals[0](); await flush();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, '/status/');
    assert.equal(calls[0].options.cache, 'no-store');
});

test('cancellation remains clickable while the AI request is pending', async () => {
    const calls = []; let finishProcess;
    const ui = setup((url, options) => {
        calls.push({url, options});
        if (url === '/process/') return new Promise(resolve => { finishProcess = resolve; });
        return Promise.resolve(response('failed', {message: 'Cancelled'}));
    }, 'failed');
    const processing = ui.events.click({target: ui.button});
    assert.equal(ui.status.textContent, 'AI nuskaito čekį...');
    const cancel = ui.actions.querySelector('.receipt-cancel');
    assert.ok(cancel);
    await ui.events.click({target: cancel});
    assert.equal(ui.status.textContent, 'failed');
    assert.equal(calls[1].url, '/cancel/');
    assert.equal(calls[1].options.headers['X-Requested-With'], 'XMLHttpRequest');
    assert.equal(calls[0].options.body.get('expected_attempt'), '1');
    finishProcess(response('failed', {message: 'Cancelled'})); await processing;
    assert.equal(calls.filter(call => call.url === '/process/').length, 1);
});

test('a stale polling response cannot restore processing after cancellation', async () => {
    let finishPoll;
    const ui = setup(url => url === '/status/' ? new Promise(resolve => { finishPoll = resolve; })
        : Promise.resolve(response('failed', {message: 'Cancelled'})));
    ui.intervals[0]();
    await ui.events.click({target: ui.button});
    finishPoll(response('processing')); await flush();
    assert.equal(ui.status.textContent, 'failed');
    assert.equal(ui.actions.querySelector('.receipt-cancel'), null);
});

test('deleted receipts disappear from polling instead of triggering new AI work', async () => {
    const ui = setup(async () => ({status: 404, ok: false, redirected: false}));
    ui.intervals[0](); await flush();
    assert.equal(ui.status.textContent, 'Čekis ištrintas');
    assert.equal(ui.actions.children.length, 0);
});
