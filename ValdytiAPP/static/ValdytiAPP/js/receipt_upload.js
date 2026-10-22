(() => {
    'use strict';
    const form = document.getElementById('receipt-upload-form');
    const input = document.getElementById('receipt-images');
    const submit = document.getElementById('receipt-submit');
    const progress = document.getElementById('receipt-progress');
    const queue = document.getElementById('receipt-queue');
    const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
    let busy = false;
    const watching = new Map();

    function cardFrom(root) {
        return {root, status: root.querySelector('.receipt-row-status') || root.children[1],
            message: root.querySelector('.receipt-row-message') || root.querySelector('p'),
            date: root.querySelector('.receipt-row-date'),
            actions: root.querySelector('.receipt-row-actions') || root.querySelector('.button-group')};
    }

    async function post(url, body) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 150000);
        try {
            const response = await fetch(url, {method: 'POST', body, signal: controller.signal,
                credentials: 'same-origin', headers: {'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest'}});
            if (response.redirected) throw new Error('Sesija baigėsi. Prisijunkite iš naujo ir atnaujinkite čekių sąrašą.');
            let data;
            try { data = await response.json(); }
            catch { throw new Error('Serveris negrąžino atsakymo. Atnaujinkite sąrašą prieš bandydami dar kartą.'); }
            if (!response.ok && !data.id) throw new Error(data.error || 'Nepavyko įkelti nuotraukos.');
            return data;
        } finally { clearTimeout(timeout); }
    }

    function show(card, data) {
        watching.delete(card.root);
        card.status.textContent = data.label;
        card.message.textContent = data.message || '';
        if (card.date) card.date.textContent = data.date || '—';
        card.actions.replaceChildren();
        const link = document.createElement('a');
        link.href = data.review_url;
        link.textContent = data.status === 'review' ? 'Patikrinti ir pataisyti' : 'Peržiūrėti čekį';
        card.actions.append(link);
        if (['uploaded', 'failed'].includes(data.status)) {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'button button-secondary receipt-retry';
            button.dataset.url = data.process_url; button.textContent = 'Bandyti nuskaityti';
            button.dataset.statusUrl = data.status_url; button.dataset.cancelUrl = data.cancel_url;
            button.dataset.attempt = data.attempt;
            card.actions.append(button);
        }
        if (data.status === 'processing') {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'button button-secondary receipt-cancel';
            button.dataset.url = data.cancel_url; button.textContent = 'Atšaukti nuskaitymą';
            card.actions.append(button);
            watching.set(card.root, {card, url: data.status_url});
        }
    }

    async function refreshStatus(entry) {
        if (entry.pending) return;
        entry.pending = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(entry.url, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
            if (response.redirected) return;
            if (response.status === 404 || response.status === 410) {
                if (watching.get(entry.card.root) !== entry) return;
                watching.delete(entry.card.root);
                entry.card.status.textContent = 'Čekis ištrintas'; entry.card.actions.replaceChildren(); return;
            }
            if (!response.ok) return;
            const data = await response.json();
            if (watching.get(entry.card.root) === entry) show(entry.card, data);
        } catch { /* A transient connection failure must not restart the paid AI request. */ }
        finally { entry.pending = false; clearTimeout(timeout); }
    }
    for (const root of document.querySelectorAll('tr[data-status="processing"]')) {
        watching.set(root, {card: cardFrom(root), url: root.dataset.statusUrl});
    }
    setInterval(() => { for (const entry of watching.values()) refreshStatus(entry); }, 5000);

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        const files = Array.from(input.files);
        if (!files.length) return;
        if (files.length > Number(form.dataset.maxFiles)) {
            progress.textContent = `Vienu kartu pasirinkite ne daugiau kaip ${form.dataset.maxFiles} nuotraukų.`; return;
        }
        if (files.some(file => file.size > Number(form.dataset.maxBytes))) {
            progress.textContent = 'Viena iš nuotraukų viršija leidžiamą failo dydį.'; return;
        }
        busy = true; submit.disabled = true; input.disabled = true;
        const pending = [];
        try {
            for (let i = 0; i < files.length; i++) {
                progress.textContent = `Išsaugoma ${i + 1} / ${files.length}`;
                const root = document.createElement('div'); root.className = 'receipt-queue-item';
                const title = document.createElement('strong'); title.textContent = files[i].name;
                const status = document.createElement('span'); status.textContent = 'Įkeliama...';
                const message = document.createElement('p');
                const actions = document.createElement('div'); actions.className = 'button-group';
                root.append(title, status, message, actions); queue.append(root);
                const card = {root, status, message, actions};
                try {
                    const payload = new FormData(); payload.append('image', files[i]);
                    const data = await post(form.dataset.url, payload);
                    show(card, data);
                    if (['uploaded', 'failed'].includes(data.status)) pending.push({card, data});
                } catch (error) { status.textContent = 'Nepavyko įkelti'; message.textContent = error.message; }
            }
            const processed = new Set();
            for (let i = 0; i < pending.length; i++) {
                const {card, data} = pending[i];
                progress.textContent = `Nuskaitoma ${i + 1} / ${pending.length}`;
                card.status.textContent = 'AI nuskaito čekį...';
                try {
                    if (processed.has(data.id)) { card.status.textContent = 'Tas pats čekis jau apdorotas šiame įkėlime'; continue; }
                    processed.add(data.id);
                    show(card, {...data, status: 'processing', label: 'AI nuskaito čekį...'});
                    show(card, await post(data.process_url, new URLSearchParams({expected_attempt: data.attempt})));
                } catch (error) {
                    card.status.textContent = 'Nuskaitymas nutrūko';
                    card.message.textContent = error.message + ' Originalas išsaugotas; atnaujinkite čekių sąrašą.';
                }
            }
            progress.textContent = 'Baigta. Rezultatai rodomi prie kiekvienos nuotraukos.';
        } finally { busy = false; submit.disabled = false; input.disabled = false; }
    });

    document.addEventListener('click', async event => {
        const cancel = event.target.closest('.receipt-cancel');
        if (cancel) {
            cancel.disabled = true;
            const card = cardFrom(cancel.closest('.receipt-queue-item, tr'));
            try { show(card, await post(cancel.dataset.url)); }
            catch (error) { card.message.textContent = error.message; cancel.disabled = false; }
            return;
        }
        const button = event.target.closest('.receipt-retry');
        if (!button || busy) return;
        busy = true; button.disabled = true;
        const root = button.closest('.receipt-queue-item, tr');
        const card = cardFrom(root);
        const url = button.dataset.url;
        const attempt = button.dataset.attempt;
        show(card, {status: 'processing', label: 'AI nuskaito čekį...',
            review_url: root.querySelector('a').href, status_url: button.dataset.statusUrl,
            cancel_url: button.dataset.cancelUrl});
        try { show(card, await post(url, new URLSearchParams({expected_attempt: attempt}))); }
        catch (error) { card.status.textContent = 'Nuskaitymas nutrūko'; card.message.textContent = error.message; }
        finally { busy = false; button.disabled = false; }
    });
    window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });
})();
