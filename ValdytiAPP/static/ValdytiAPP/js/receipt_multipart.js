(() => {
    'use strict';
    const form = document.getElementById('receipt-multipart-form');
    if (!form) return;
    const input = document.getElementById('receipt-part-images');
    const order = document.getElementById('receipt-part-order');
    const submit = document.getElementById('receipt-multipart-submit');
    const progress = document.getElementById('receipt-multipart-progress');
    const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
    let files = [], busy = false;
    function renderOrder() {
        order.replaceChildren();
        files.forEach((file, index) => {
            const li = document.createElement('li');
            const name = document.createElement('span'); name.textContent = `${index + 1}. ${file.name}`;
            li.append(name);
            for (const [label, direction] of [['Aukštyn', -1], ['Žemyn', 1]]) {
                const button = document.createElement('button'); button.type = 'button';
                button.className = 'button button-secondary'; button.textContent = label;
                button.setAttribute('aria-label', `${file.name}: ${label.toLowerCase()}`);
                button.disabled = busy || index + direction < 0 || index + direction >= files.length;
                button.addEventListener('click', () => {
                    if (busy) return;
                    [files[index], files[index + direction]] = [files[index + direction], files[index]];
                    renderOrder();
                }); li.append(button);
            }
            order.append(li);
        });
    }
    input.addEventListener('change', () => { files = Array.from(input.files); renderOrder(); });
    const publish = data => document.dispatchEvent(new CustomEvent('receipt-group-updated', {detail: data}));
    async function post(url, body) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 150000);
        try {
            const response = await fetch(url, {method: 'POST', body, credentials: 'same-origin',
                signal: controller.signal, headers: {'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest'}});
            if (response.redirected) throw new Error('Sesija baigėsi. Prisijunkite iš naujo.');
            let data;
            try { data = await response.json(); }
            catch { throw new Error('Serveris neatsakė. Patikrinkite čekių sąrašą prieš kartodami.'); }
            if (!response.ok && !data.id) throw new Error(data.error || 'Nepavyko įkelti čekio dalių.');
            return data;
        } finally { clearTimeout(timeout); }
    }
    form.addEventListener('submit', async event => {
        event.preventDefault(); if (busy) return;
        if (files.length < 2 || files.length > 6) {
            progress.textContent = 'Vienam čekiui pasirinkite 2–6 nuotraukas.'; return;
        }
        if (files.some(file => file.size > Number(form.dataset.maxBytes))) {
            progress.textContent = 'Viena nuotrauka viršija leidžiamą dydį.'; return;
        }
        busy = true; input.disabled = true; submit.disabled = true; renderOrder();
        let receipt;
        try {
            progress.textContent = 'Tikrinamos pasirinktos dalys...';
            const manifest = [];
            for (const file of files) {
                const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
                manifest.push({name: file.name, size: file.size,
                    hash: Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('')});
            }
            if (new Set(manifest.map(item => item.hash)).size !== files.length) {
                throw new Error('Ta pati nuotrauka pasirinkta kelis kartus. Palikite tik skirtingas dalis.');
            }
            receipt = await post(form.dataset.url, new URLSearchParams({manifest: JSON.stringify(manifest)}));
            publish(receipt);
            if (!receipt.upload_complete) {
                for (let index = 0; index < files.length; index++) {
                    progress.textContent = `Išsaugoma vieno čekio dalis ${index + 1} / ${files.length}`;
                    const target = receipt.part_uploads.find(part => part.hash === manifest[index].hash);
                    if (!target) throw new Error('Nepavyko suderinti dalių. Pasirinkite visas nuotraukas iš naujo.');
                    const body = new FormData(); body.append('image', files[index]);
                    receipt = await post(target.url, body); publish(receipt);
                }
            }
            if (receipt.upload_complete && ['uploaded', 'failed'].includes(receipt.status)) {
                progress.textContent = 'AI sujungia dalis ir nuskaito VIENĄ čekį...';
                publish({...receipt, status: 'processing', label: 'AI sujungia vieno čekio dalis...'});
                receipt = await post(receipt.process_url, new URLSearchParams({expected_attempt: receipt.attempt}));
                publish(receipt);
            }
            progress.textContent = `Baigta: ${receipt.label}. Rezultatas pateiktas žemiau.`;
        } catch (error) {
            progress.textContent = error.message + ' Jei įkėlimas nutrūko, pasirinkite visas tas pačias dalis — bus tęsiamas tas pats įrašas.';
        } finally { busy = false; input.disabled = false; submit.disabled = false; renderOrder(); }
    });
    window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });
})();
