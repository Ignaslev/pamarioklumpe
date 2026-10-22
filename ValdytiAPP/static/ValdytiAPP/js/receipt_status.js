(() => {
    'use strict';
    const panel = document.getElementById('receipt-processing');
    if (!panel) return;
    let pending = false;
    const timer = setInterval(async () => {
        if (pending) return;
        pending = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(panel.dataset.statusUrl, {
                credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
            if (response.redirected) { clearInterval(timer); return; }
            if (!response.ok) return;
            const data = await response.json();
            if (data.status !== 'processing') { clearInterval(timer); window.location.reload(); }
        } catch { /* Never repeat a paid AI request just to check its status. */ }
        finally { pending = false; clearTimeout(timeout); }
    }, 5000);
})();
