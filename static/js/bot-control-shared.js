(function () {
    const BOT_ID = 'gwarodollarprinter';
    const DEFAULT_STATUS = {
        success: false,
        message: 'No action yet.',
        status: 'Stopped',
        uptime: '0s',
        last_signal: 'No signal yet',
        mt5_connected: false,
    };

    function getCsrfToken() {
        const node = document.querySelector('meta[name="csrf-token"]');
        return node ? node.content : '';
    }

    function buildPayload(payload, fallback) {
        const data = payload || {};
        return {
            success: Boolean(data.success ?? data.ok),
            message: data.message || fallback.message,
            status: data.status || fallback.status,
            uptime: data.uptime || fallback.uptime,
            last_signal: data.last_signal || fallback.last_signal,
            mt5_connected: data.mt5_connected ?? data.mt5_connected ?? fallback.mt5_connected,
            ...data,
        };
    }

    async function requestJson(path, options = {}) {
        const response = await fetch(path, {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken(),
                ...(options.headers || {}),
            },
            ...options,
        });
        const text = await response.text();
        try {
            return { ok: response.ok, response, data: JSON.parse(text || '{}') };
        } catch (error) {
            return { ok: response.ok, response, data: { ok: false, message: 'Non-JSON response from server', raw: text } };
        }
    }

    async function refreshStatus() {
        const result = await requestJson('/api/bot/status', { method: 'GET' });
        const data = result.data || {};
        const payload = buildPayload(data, DEFAULT_STATUS);
        window.__gwaroBotState = payload;
        window.dispatchEvent(new CustomEvent('gwaro:status-updated', { detail: payload }));
        return payload;
    }

    async function runAction(endpoint, actionLabel, method = 'POST', body = {}) {
        const button = document.activeElement && document.activeElement instanceof HTMLElement ? document.activeElement : null;
        if (button && button.dataset && button.dataset.controlName) {
            button.disabled = true;
            button.classList.add('is-loading');
        }
        try {
            const result = await requestJson(endpoint, {
                method,
                body: method === 'GET' ? undefined : JSON.stringify({ bot_id: BOT_ID, ...body }),
            });
            const payload = buildPayload(result.data || {}, DEFAULT_STATUS);
            await refreshStatus();
            window.dispatchEvent(new CustomEvent('gwaro:action-complete', { detail: { ...payload, actionLabel } }));
            return payload;
        } finally {
            if (button && button.dataset && button.dataset.controlName) {
                button.disabled = false;
                button.classList.remove('is-loading');
            }
        }
    }

    async function startBot() {
        return runAction('/api/bot/start', 'Starting bot');
    }

    async function stopBot() {
        return runAction('/api/bot/stop', 'Stopping bot');
    }

    async function restartBot() {
        return runAction('/api/bot/restart', 'Restarting bot');
    }

    async function closeAllTrades() {
        return runAction('/api/bot/close-all', 'Closing trades');
    }

    async function breakEven() {
        return runAction('/api/bot/breakeven', 'Applying break-even');
    }

    window.GwaroBotControl = {
        startBot,
        stopBot,
        restartBot,
        closeAllTrades,
        breakEven,
        refreshStatus,
        requestJson,
    };
})();
