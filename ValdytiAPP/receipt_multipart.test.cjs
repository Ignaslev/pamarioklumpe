// Test the separate multipart form without a browser or external service.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
class Element {
    constructor() { this.children = []; this.dataset = {}; this.events = {}; this.disabled = false; this.textContent = ''; }
    append(...children) { this.children.push(...children); }
    replaceChildren() { this.children = []; }
    addEventListener(name, fn) { this.events[name] = fn; }
    setAttribute() {}
    querySelector() { return {value: 'csrf-test'}; }
}
function file(name, content) {
    const bytes = new TextEncoder().encode(content);
    return {name, size: bytes.length, arrayBuffer: async () => bytes.buffer};
}
const selected = [file('top.jpg', 'top photo'), file('bottom.jpg', 'bottom photo')];
function data(overrides = {}) {
    return {id: 5, filename: 'One receipt', status: 'uploaded', label: 'Uploaded', attempt: 0,
        upload_complete: false, process_url: '/process/', review_url: '/review/', status_url: '/status/',
        cancel_url: '/cancel/', ...overrides};
}
const ok = value => ({ok: true, redirected: false, json: async () => value});
function setup(fetch) {
    const ids = Object.fromEntries(['receipt-multipart-form', 'receipt-part-images', 'receipt-part-order',
        'receipt-multipart-submit', 'receipt-multipart-progress'].map(id => [id, new Element()]));
    const form = ids['receipt-multipart-form']; form.dataset = {url: '/create/', maxBytes: '15728640'};
    const input = ids['receipt-part-images']; input.files = selected;
    const published = [];
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/ValdytiAPP/js/receipt_multipart.js'), 'utf8'), {
        document: {getElementById: id => ids[id], createElement: () => new Element(), dispatchEvent: event => published.push(event.detail)},
        CustomEvent: class {constructor(name, options) {this.type = name; this.detail = options.detail;}},
        fetch, crypto: webcrypto, Uint8Array, URLSearchParams, AbortController,
        FormData: class {constructor() {this.values = {};} append(key, value) {this.values[key] = value;}},
        window: {addEventListener() {}}, setTimeout: () => 1, clearTimeout() {},
    });
    input.events.change();
    return {ids, form, input, published, submit: () => form.events.submit({preventDefault() {}})};
}

test('ordered photos upload separately, then exactly one receipt is processed', async () => {
    const calls = []; let manifest;
    const ui = setup(async (url, options) => {
        calls.push({url, options});
        if (url === '/create/') {
            manifest = JSON.parse(options.body.get('manifest'));
            return ok(data({part_uploads: manifest.map((part, i) => ({hash: part.hash, url: `/part/${i + 1}/`}))}));
        }
        const part_uploads = manifest.map((part, i) => ({hash: part.hash, url: `/part/${i + 1}/`}));
        if (url === '/part/1/') return ok(data({part_uploads}));
        if (url === '/part/2/') return ok(data({part_uploads, upload_complete: true}));
        return ok(data({status: 'ready', label: 'Ready', upload_complete: true}));
    });
    // Move bottom to top to prove the user-defined sequence is what the server receives.
    ui.ids['receipt-part-order'].children[1].children[1].events.click();
    await ui.submit();
    assert.deepEqual(manifest.map(item => item.name), ['bottom.jpg', 'top.jpg']);
    assert.ok(manifest.every(item => /^[0-9a-f]{64}$/.test(item.hash)));
    assert.deepEqual(calls.map(call => call.url), ['/create/', '/part/1/', '/part/2/', '/process/']);
    assert.equal(calls[1].options.body.values.image.name, 'bottom.jpg');
    assert.equal(calls[3].options.body.get('expected_attempt'), '0');
    assert.equal(ui.published.at(-1).status, 'ready');
    assert.equal(ui.input.disabled, false);
});

test('an interrupted part upload never starts AI extraction', async () => {
    const calls = []; let manifest;
    const ui = setup(async (url, options) => {
        calls.push(url);
        if (url === '/create/') {
            manifest = JSON.parse(options.body.get('manifest'));
            return ok(data({part_uploads: manifest.map((part, i) => ({hash: part.hash, url: `/part/${i + 1}/`}))}));
        }
        if (url === '/part/1/') return ok(data({part_uploads: manifest.map((part, i) => ({hash: part.hash, url: `/part/${i + 1}/`}))}));
        return {ok: false, redirected: false, json: async () => ({error: 'Upload failed'})};
    });
    await ui.submit();
    assert.equal(calls.includes('/process/'), false);
    assert.match(ui.ids['receipt-multipart-progress'].textContent, /tas pačias dalis/);
    assert.equal(ui.input.disabled, false);
});

test('identical photos and wrong selection size are rejected before uploading', async () => {
    const calls = [];
    const ui = setup(async url => {calls.push(url); throw new Error('Should not call');});
    ui.input.files = [selected[0]]; ui.input.events.change(); await ui.submit();
    assert.match(ui.ids['receipt-multipart-progress'].textContent, /2–6/);
    ui.input.files = [selected[0], file('copy.jpg', 'top photo')]; ui.input.events.change(); await ui.submit();
    assert.match(ui.ids['receipt-multipart-progress'].textContent, /Ta pati nuotrauka/);
    assert.equal(calls.length, 0);
});

test('already completed photo group is reused without uploading or another AI call', async () => {
    const calls = [];
    const ui = setup(async url => {calls.push(url); return ok(data({status: 'ready', label: 'Ready', upload_complete: true}));});
    await ui.submit();
    assert.deepEqual(calls, ['/create/']);
    assert.equal(ui.published.at(-1).status, 'ready');
});
