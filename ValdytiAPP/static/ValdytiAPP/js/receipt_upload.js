(() => {
    'use strict';
    const form = document.getElementById('receipt-upload-form');
    const input = document.getElementById('receipt-images');
    const submit = document.getElementById('receipt-submit');
    const progress = document.getElementById('receipt-progress');
    const queue = document.getElementById('receipt-queue');
    const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
    let busy = false;

    async function post(url, body) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 150000);
        try {
            const response = await fetch(url, {method: 'POST', body, signal: controller.signal,
                credentials: 'same-origin', headers: {'X-CSRFToken': csrf}});
            if (response.redirected) throw new Error('Sesija baigėsi. Prisijunkite iš naujo ir atnaujinkite čekių sąrašą.');
            let data;
            try { data = await response.json(); }
            catch { throw new Error('Serveris negrąžino atsakymo. Atnaujinkite sąrašą prieš bandydami dar kartą.'); }
            if (!response.ok && !data.id) throw new Error(data.error || 'Nepavyko įkelti nuotraukos.');
            return data;
        } finally { clearTimeout(timeout); }
    }

    function show(card, data) {
        card.status.textContent = data.label;
        card.message.textContent = data.message || '';
        card.actions.replaceChildren();
        const link = document.createElement('a');
        link.href = data.review_url;
        link.textContent = data.status === 'review' ? 'Patikrinti ir pataisyti' : 'Peržiūrėti čekį';
        card.actions.append(link);
        if (['uploaded', 'failed', 'processing'].includes(data.status)) {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'button button-secondary receipt-retry';
            button.dataset.url = data.process_url; button.textContent = 'Bandyti nuskaityti';
            card.actions.append(button);
        }
    }

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
                const card = {status, message, actions};
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
                    show(card, await post(data.process_url));
                } catch (error) {
                    card.status.textContent = 'Nuskaitymas nutrūko';
                    card.message.textContent = error.message + ' Originalas išsaugotas; atnaujinkite čekių sąrašą.';
                }
            }
            progress.textContent = 'Baigta. Rezultatai rodomi prie kiekvienos nuotraukos.';
        } finally { busy = false; submit.disabled = false; input.disabled = false; }
    });

    document.addEventListener('click', async event => {
        const button = event.target.closest('.receipt-retry');
        if (!button || busy) return;
        busy = true; button.disabled = true;
        const root = button.closest('.receipt-queue-item, tr');
        const card = {status: root.querySelector('.receipt-row-status') || root.children[1],
            message: root.querySelector('.receipt-row-message') || root.querySelector('p'),
            actions: root.querySelector('.receipt-row-actions') || root.querySelector('.button-group')};
        card.status.textContent = 'AI nuskaito čekį...';
        try { show(card, await post(button.dataset.url)); }
        catch (error) { card.status.textContent = 'Nuskaitymas nutrūko'; card.message.textContent = error.message; }
        finally { busy = false; button.disabled = false; }
    });
    window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });
})();
