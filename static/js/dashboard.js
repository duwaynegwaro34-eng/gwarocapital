//==============================
// GWARO CAPITAL DASHBOARD
//==============================

const seenNotificationIds = new Set();
const chartInstances = {};

function csrfToken() {
    const node = document.querySelector('meta[name="csrf-token"]');
    return node ? node.content : "";
}

async function updateDashboard(){

    try{

        const [accountResponse, statusResponse] = await Promise.all([
            fetch("/api/mt5/account"),
            fetch("/api/mt5/status")
        ]);
        const data = await accountResponse.json();
        const terminal = await statusResponse.json();

        if(document.getElementById("balance"))
            document.getElementById("balance").innerHTML =
            terminal.connected ? "$"+Number(data.balance).toFixed(2) : "Disconnected";

        if(document.getElementById("equity"))
            document.getElementById("equity").innerHTML =
            terminal.connected ? "$"+Number(data.equity).toFixed(2) : "Disconnected";

        if(document.getElementById("profit"))
            document.getElementById("profit").innerHTML =
            terminal.connected ? "$"+Number(data.profit).toFixed(2) : "Disconnected";

        if(document.getElementById("status"))
            document.getElementById("status").innerHTML = terminal.status;

        const pill = document.getElementById("connection-pill");
        const dot = document.getElementById("connection-dot");
        const badge = document.getElementById("mt5-connection-badge");

        if (pill && dot) {
            const disconnected = !terminal.connected;
            pill.classList.toggle("disconnected", disconnected);
            dot.classList.toggle("disconnected", disconnected);
        }

        if (badge) {
            badge.innerHTML = terminal.connected ? "Active" : "Disconnected";
        }

        const accountField = document.getElementById("account-number");
        const accountNameField = document.getElementById("account-name");
        const brokerField = document.getElementById("broker-name");
        const serverField = document.getElementById("server-name");
        const freeMarginField = document.getElementById("free-margin");
        const marginField = document.getElementById("margin-value");
        const leverageField = document.getElementById("leverage-value");
        const currencyField = document.getElementById("currency-value");
        const floatingField = document.getElementById("floating-pl");
        const mt5StatusLabel = document.getElementById("mt5-status-label");
        const mt5StatusLogin = document.getElementById("mt5-status-login");
        const mt5StatusServer = document.getElementById("mt5-status-server");
        const mt5ConnectionTime = document.getElementById("mt5-connection-time");

        if (accountField) accountField.innerHTML = terminal.connected ? (data.account || '--') : 'Disconnected';
        if (accountNameField) accountNameField.innerHTML = terminal.connected ? (data.account_name || '--') : 'Disconnected';
        if (brokerField) brokerField.innerHTML = terminal.connected ? (data.broker || '--') : 'Disconnected';
        if (serverField) serverField.innerHTML = terminal.connected ? (data.server || '--') : 'Disconnected';
        if (freeMarginField) freeMarginField.innerHTML = terminal.connected ? ("$" + Number(data.free_margin).toFixed(2)) : 'Disconnected';
        if (marginField) marginField.innerHTML = terminal.connected ? ("$" + Number(data.margin).toFixed(2)) : 'Disconnected';
        if (leverageField) leverageField.innerHTML = terminal.connected ? (data.leverage || '--') : 'Disconnected';
        if (currencyField) currencyField.innerHTML = terminal.connected ? (data.currency || '--') : 'Disconnected';
        if (floatingField) floatingField.innerHTML = terminal.connected ? ("$" + Number(data.floating_profit).toFixed(2)) : 'Disconnected';
        if (mt5StatusLabel) mt5StatusLabel.innerHTML = terminal.status || 'Disconnected';
        if (mt5StatusLogin) mt5StatusLogin.innerHTML = terminal.connected ? (terminal.account_login || '--') : '--';
        if (mt5StatusServer) mt5StatusServer.innerHTML = terminal.connected ? (terminal.server || '--') : '--';
        if (mt5ConnectionTime) mt5ConnectionTime.innerHTML = terminal.connected ? (terminal.connection_time || '--') : '--';

    }

    catch(err){

        console.log(err);

    }

}

async function updateMarket(){

    try{

        const response = await fetch("/market_data");

        const data = await response.json();

        const marketContainer = document.getElementById("market-data");
        if (!marketContainer) {
            updateTicker(data);
            return;
        }

        let html="";

        if(data.markets){

            data.markets.forEach(item=>{

                html+=`

                <div class="market-item">

                    <div>

                        <strong>${item.symbol}</strong>

                    </div>

                    <div>

                        Bid ${item.bid}<br>

                        Ask ${item.ask}

                    </div>

                </div>

                `;

            });

        }

        marketContainer.innerHTML=html;

    }

    catch(err){

        console.log(err);

    }

}

async function updatePositions(){

    try{

        const response = await fetch("/api/mt5/positions");

        const positions = await response.json();

        let html="";

        if (!positions.length) {
            html = '<tr><td colspan="10" style="color:#8f8f8f;">No open positions</td></tr>';
        } else {
            positions.forEach(position=>{

                html+=`

                <tr>
                    console.debug('postAction: sending', path, body);
                    const res = await fetch(path, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken()},
                        body: JSON.stringify(body)
                    });
                    let text = await res.text();
                    try{
                        const json = JSON.parse(text || '{}');
                        console.debug('postAction: received', path, json);
                        return json;
                    }catch(e){
                        console.warn('postAction: non-JSON response', path, text);
                        return { ok: false, message: 'Non-JSON response from server', raw: text };
                    }
                }catch(err){
                    console.error('postAction: fetch error', path, err);
                    return { ok: false, message: 'Network error', error: String(err) };
                    <td>${position.current_price || '--'}</td>
                    <td>${position.sl || '--'}</td>
                    <td>${position.tp || '--'}</td>
                    <td>$${position.profit || '0.00'}</td>
                    <td>${position.open_time || '--'}</td>

                </tr>

                `;

            });
        }

        document.getElementById("positions").innerHTML=html;

    }

    catch(err){

        console.log(err);

    }

}

async function updateSignals(){

    try{

        const response=await fetch("/signals");

        const signals=await response.json();

        let html="";

        if (!signals.length) {
            html = '<div class="signal-item"><p>No signals available right now.</p></div>';
        } else {
            signals.forEach(signal=>{

                html+=`

                <div class="signal-item">
                    <div class="signal-row">
                        <strong>${signal.symbol}</strong>
                        <span class="signal-pill ${signal.signal.toLowerCase()}">${signal.signal}</span>
                    </div>
                    <p>Entry: ${signal.entry} · SL: ${signal.sl} · TP: ${signal.tp}</p>
                    <small>Confidence: ${signal.confidence}%</small>
                </div>

                `;

            });
        }

        document.getElementById("signals").innerHTML=html;

    }

    catch(err){

        console.log(err);

    }

}

async function updateBotLog(){

    try{

        const response = await fetch("/api/bot/status");
        const data = await response.json();

        const botStatusNodes = document.querySelectorAll("#bot-status");
        const botLabel = document.getElementById("current-bot-label");
        const startTime = document.getElementById("bot-start-time");
        const uptime = document.getElementById("bot-uptime");
        const lastExecution = document.getElementById("bot-last-execution");
        const lastSignal = document.getElementById("bot-last-signal");
        const lastTrade = document.getElementById("bot-last-trade-result");
        const selector = document.getElementById("bot-selector");

        botStatusNodes.forEach((node) => {
            node.innerHTML = data.status || "Stopped";
        });
        if (botLabel) botLabel.innerHTML = data.current_bot || "--";
        if (startTime) startTime.innerHTML = data.start_time || "--";
        if (uptime) uptime.innerHTML = data.uptime || "00:00:00";
        if (lastExecution) lastExecution.innerHTML = data.last_execution || "--";
        if (lastSignal) lastSignal.innerHTML = data.last_signal || "--";
        if (lastTrade) lastTrade.innerHTML = data.last_trade_result || "--";
        if (selector && data.current_bot_id) selector.value = data.current_bot_id;

        const consoleBox = document.getElementById("bot-console");
        if (consoleBox) {
            const activity = Array.isArray(data.activity_log) ? data.activity_log : [];
            if (!activity.length) {
                consoleBox.innerHTML = '<div class="console-line">No activity yet.</div>';
            } else {
                const iconByType = {
                    "Bot Started": "🟢",
                    "Bot Stopped": "🔴",
                    "Trade Opened": "📈",
                    "Trade Closed": "📉",
                    "Errors": "⚠️",
                };

                consoleBox.innerHTML = activity.map((event) => {
                    const eventType = event.type || "Info";
                    const icon = iconByType[eventType] || "ℹ️";
                    const timestamp = event.time ? new Date(event.time).toLocaleTimeString() : "--:--:--";
                    const message = event.message || "-";
                    return `<div class="console-line"><span class="console-time">${timestamp}</span>${icon} ${message}</div>`;
                }).join("");
            }
        }

    }

    catch(err){

        console.log(err);

    }

}

async function updateAssistantSummary(){

    try {

        const response = await fetch("/api/assistant/summary");
        const data = await response.json();

        const aiSummary = data.ai_summary || {};
        const analysis = Array.isArray(data.ai_trade_analysis) ? data.ai_trade_analysis : [];
        const risk = data.risk_manager || {};
        const perf = data.performance || {};
        const today = data.today_performance || {};
        const activeBot = data.active_bot_summary || {};
        const notifications = Array.isArray(data.notifications) ? data.notifications : [];

        const openTradeCount = document.getElementById("ai-open-trade-count");
        const highConfidence = document.getElementById("ai-high-confidence");
        const holdCount = document.getElementById("ai-hold-count");
        const analysisBox = document.getElementById("ai-trade-analysis");

        if (openTradeCount) openTradeCount.innerHTML = `${aiSummary.open_trade_count || 0} Trades`;
        if (highConfidence) highConfidence.innerHTML = aiSummary.high_confidence_signals || 0;
        if (holdCount) holdCount.innerHTML = aiSummary.hold_count || 0;

        if (analysisBox) {
            if (!analysis.length) {
                analysisBox.innerHTML = '<div class="signal-item"><p>No open trades to analyze.</p></div>';
            } else {
                analysisBox.innerHTML = analysis.map((item) => {
                    const recommendation = item.recommendation || "HOLD";
                    const cls = recommendation.toLowerCase() === "buy" ? "buy" : (recommendation.toLowerCase() === "sell" ? "sell" : "hold");
                    return `
                        <div class="signal-item">
                            <div class="signal-row">
                                <strong>${item.symbol || '--'} #${item.ticket || '--'}</strong>
                                <span class="signal-pill ${cls}">${recommendation}</span>
                            </div>
                            <p>Confidence: ${item.confidence || 0}% · Profit: $${Number(item.profit || 0).toFixed(2)}</p>
                            <small>${item.reason || '-'}</small>
                        </div>
                    `;
                }).join("");
            }
        }

        const riskLot = document.getElementById("risk-recommended-lot");
        const riskPct = document.getElementById("risk-current-percent");
        const riskLimit = document.getElementById("risk-limit-percent");
        const riskWarning = document.getElementById("risk-warning");

        if (riskLot) riskLot.innerHTML = Number(risk.recommended_lot_size || 0.01).toFixed(2);
        if (riskPct) riskPct.innerHTML = `${Number(risk.current_risk_percent || 0).toFixed(2)}%`;
        if (riskLimit) riskLimit.innerHTML = `${Number(risk.risk_limit_percent || 2.0).toFixed(2)}%`;
        if (riskWarning) riskWarning.innerHTML = risk.warning || "Risk is within configured limits.";

        const perfWinRate = document.getElementById("perf-win-rate");
        const perfTotalTrades = document.getElementById("perf-total-trades");
        const perfWinningTrades = document.getElementById("perf-winning-trades");
        const perfLosingTrades = document.getElementById("perf-losing-trades");
        const perfNetProfit = document.getElementById("perf-net-profit");
        const perfProfitFactor = document.getElementById("perf-profit-factor");
        const perfDrawdown = document.getElementById("perf-max-drawdown");

        if (perfWinRate) perfWinRate.innerHTML = `${Number(perf.win_rate || 0).toFixed(2)}%`;
        if (perfTotalTrades) perfTotalTrades.innerHTML = perf.total_trades || 0;
        if (perfWinningTrades) perfWinningTrades.innerHTML = perf.winning_trades || 0;
        if (perfLosingTrades) perfLosingTrades.innerHTML = perf.losing_trades || 0;
        if (perfNetProfit) perfNetProfit.innerHTML = `$${Number(perf.net_profit || 0).toFixed(2)}`;
        if (perfProfitFactor) perfProfitFactor.innerHTML = Number(perf.profit_factor || 0).toFixed(2);
        if (perfDrawdown) perfDrawdown.innerHTML = `$${Number(perf.maximum_drawdown || 0).toFixed(2)}`;

        const todayDate = document.getElementById("today-date");
        const todayWinRate = document.getElementById("today-win-rate");
        const todayTotalTrades = document.getElementById("today-total-trades");
        const todayNetProfit = document.getElementById("today-net-profit");

        if (todayDate) todayDate.innerHTML = today.date || "Today";
        if (todayWinRate) todayWinRate.innerHTML = `${Number(today.win_rate || 0).toFixed(2)}%`;
        if (todayTotalTrades) todayTotalTrades.innerHTML = today.total_trades || 0;
        if (todayNetProfit) todayNetProfit.innerHTML = `$${Number(today.net_profit || 0).toFixed(2)}`;

        const activeBotName = document.getElementById("active-bot-name");
        const activeBotStatus = document.getElementById("active-bot-status");
        const activeBotUptime = document.getElementById("active-bot-uptime");
        const activeBotSignal = document.getElementById("active-bot-last-signal");

        if (activeBotName) activeBotName.innerHTML = activeBot.bot || "--";
        if (activeBotStatus) activeBotStatus.innerHTML = activeBot.status || "Stopped";
        if (activeBotUptime) activeBotUptime.innerHTML = activeBot.uptime || "00:00:00";
        if (activeBotSignal) activeBotSignal.innerHTML = activeBot.last_signal || "--";

        notifications.forEach((item) => {
            const id = item.id || `${item.type || 'notification'}:${item.message || ''}`;
            if (seenNotificationIds.has(id)) return;
            seenNotificationIds.add(id);
            showNotification(item.message || item.type || "Notification", item.severity || "info");
            addConsoleLog(`🔔 ${item.type || 'Notice'}: ${item.message || ''}`);
        });

    } catch (err) {
        console.log(err);
    }
}

function formatMoney(value) {
    const number = Number(value || 0);
    return `$${number.toFixed(2)}`;
}

function formatPercent(value) {
    const number = Number(value || 0);
    return `${number.toFixed(2)}%`;
}

function updateMetric(id, value) {
    const node = document.getElementById(id);
    if (node) {
        node.innerHTML = value;
    }
}

function buildChart(canvasId, label, values, color, type = "line") {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;

    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }

    chartInstances[canvasId] = new Chart(canvas, {
        type,
        data: {
            labels: values.map((item) => item.label ?? item.time ?? ""),
            datasets: [{
                label,
                data: values.map((item) => item.value),
                borderColor: color,
                backgroundColor: color.replace("1)", "0.18)"),
                tension: 0.35,
                fill: true,
                pointRadius: 1.5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#8f8f8f" }, grid: { color: "rgba(255,255,255,0.04)" } },
                y: { ticks: { color: "#8f8f8f" }, grid: { color: "rgba(255,255,255,0.04)" } },
            },
        },
    });
}

function buildTradeHistoryUrl(page = 1) {
    const params = new URLSearchParams();
    const search = document.getElementById("trade-search")?.value || "";
    const startDate = document.getElementById("trade-start-date")?.value || "";
    const endDate = document.getElementById("trade-end-date")?.value || "";
    const symbol = document.getElementById("trade-symbol-filter")?.value || "";
    const bot = document.getElementById("trade-bot-filter")?.value || "";

    if (search) params.set("search", search);
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    if (symbol) params.set("symbol", symbol);
    if (bot) params.set("bot", bot);
    params.set("page", page);
    params.set("per_page", 20);

    return `/api/dashboard/trade-history?${params.toString()}`;
}

function renderTradeHistory(payload) {
    const body = document.getElementById("trade-history-body");
    const pagination = document.getElementById("trade-pagination");
    const count = document.getElementById("trade-history-count");
    const rows = Array.isArray(payload.items) ? payload.items : [];

    if (count) count.innerHTML = `${payload.total || rows.length || 0} Trades`;
    if (!body) return;

    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="13" style="color:#8f8f8f;">No trade history for current filters</td></tr>';
    } else {
        body.innerHTML = rows.map((item) => `
            <tr>
                <td>${item.ticket || '--'}</td>
                <td>${item.symbol || '--'}</td>
                <td>${item.side || '--'}</td>
                <td>${item.lot_size || '--'}</td>
                <td>${item.entry_price || '--'}</td>
                <td>${item.exit_price || '--'}</td>
                <td>${item.stop_loss || '--'}</td>
                <td>${item.take_profit || '--'}</td>
                <td>$${Number(item.profit_loss || 0).toFixed(2)}</td>
                <td>${item.open_time || '--'}</td>
                <td>${item.close_time || '--'}</td>
                <td>${item.duration || '--'}</td>
                <td>${item.bot_used || '--'}</td>
            </tr>
        `).join("");
    }

    if (pagination) {
        const currentPage = Number(payload.page || 1);
        const totalPages = Number(payload.total_pages || 1);
        const buttons = [];
        if (payload.has_prev) buttons.push(`<button class="pagination-btn" data-page="${currentPage - 1}">Prev</button>`);
        for (let page = Math.max(1, currentPage - 2); page <= Math.min(totalPages, currentPage + 2); page++) {
            buttons.push(`<button class="pagination-btn ${page === currentPage ? 'active' : ''}" data-page="${page}">${page}</button>`);
        }
        if (payload.has_next) buttons.push(`<button class="pagination-btn" data-page="${currentPage + 1}">Next</button>`);
        pagination.innerHTML = buttons.join("");
        pagination.querySelectorAll("button[data-page]").forEach((button) => {
            button.addEventListener("click", async () => {
                const response = await fetch(buildTradeHistoryUrl(button.dataset.page));
                const data = await response.json();
                renderTradeHistory(data);
            });
        });
    }
}

function renderNotificationCenter(items) {
    const container = document.getElementById("notification-feed");
    if (!container) return;

    if (!items.length) {
        container.innerHTML = '<div class="notification-item info"><div class="notification-type">Info</div><div>No live notifications right now.</div></div>';
        return;
    }

    container.innerHTML = items.map((item) => `
        <div class="notification-item ${item.severity || 'info'}">
            <div class="notification-type">${item.type || 'Notice'}</div>
            <div>${item.message || ''}</div>
        </div>
    `).join("");
}

async function updatePhase9Analytics() {
    try {
        const [summaryResponse, botResponse, chartResponse, tradeResponse, notificationResponse] = await Promise.all([
            fetch("/api/dashboard/summary"),
            fetch("/api/dashboard/bot-statistics"),
            fetch("/api/dashboard/chart-data"),
            fetch(buildTradeHistoryUrl()),
            fetch("/api/dashboard/notifications"),
        ]);

        const summary = await summaryResponse.json();
        const botStats = await botResponse.json();
        const charts = await chartResponse.json();
        const tradeHistory = await tradeResponse.json();
        const notifications = await notificationResponse.json();

        updateMetric("summary-today-pl", formatMoney(summary.performance?.today_profit_loss));
        updateMetric("summary-weekly-pl", formatMoney(summary.performance?.weekly_profit_loss));
        updateMetric("summary-monthly-pl", formatMoney(summary.performance?.monthly_profit_loss));
        updateMetric("summary-net-profit", formatMoney(summary.performance?.net_profit));
        updateMetric("summary-roi", formatPercent(summary.performance?.roi_percent));
        updateMetric("summary-total-trades", summary.performance?.total_trades || 0);
        updateMetric("summary-wins", summary.performance?.winning_trades || 0);
        updateMetric("summary-losses", summary.performance?.losing_trades || 0);
        updateMetric("summary-win-rate", formatPercent(summary.performance?.win_rate));
        updateMetric("summary-avg-profit", formatMoney(summary.performance?.average_profit_per_trade));
        updateMetric("summary-avg-loss", formatMoney(summary.performance?.average_loss_per_trade));
        updateMetric("summary-profit-factor", Number(summary.performance?.profit_factor || 0).toFixed(2));
        updateMetric("summary-max-drawdown", formatMoney(summary.performance?.maximum_drawdown));
        updateMetric("summary-current-drawdown", formatMoney(summary.performance?.current_drawdown));
        updateMetric("summary-floating-pl", formatMoney(summary.performance?.floating_profit_loss));

        const bestBot = summary.best_performing_bot || botStats.best_bot;
        updateMetric("best-bot-chip", `Best Bot: ${bestBot?.bot_name || bestBot?.name || "--"}`);
        updateMetric("analytics-updated", `Updated ${new Date().toLocaleTimeString()}`);

        const botGrid = document.getElementById("bot-performance-grid");
        if (botGrid && Array.isArray(botStats.items)) {
            botGrid.innerHTML = botStats.items.map((bot) => {
                const bestClass = bestBot && (bestBot.bot_id === bot.bot_id || bestBot.bot_name === bot.bot_name) ? "best" : "";
                return `
                    <div class="bot-performance-card ${bestClass}">
                        <div class="signal-row"><strong>${bot.bot_name || "--"}</strong><span class="signal-pill ${bot.running ? "buy" : "sell"}">${bot.running ? "Running" : "Stopped"}</span></div>
                        <p>Trades Today: ${bot.trades_today || 0}</p>
                        <p>Total Trades: ${bot.total_trades || 0}</p>
                        <p>Wins / Losses: ${bot.wins || 0} / ${bot.losses || 0}</p>
                        <p>Win Rate: ${Number(bot.win_rate || 0).toFixed(2)}%</p>
                        <p>Current Profit: ${formatMoney(bot.current_profit)}</p>
                        <p>Total Profit: ${formatMoney(bot.total_profit)}</p>
                        <p>Symbol: ${bot.current_symbol || "--"}</p>
                        <p>Timeframe: ${bot.current_timeframe || "--"}</p>
                        <p>Last Trade: ${bot.last_trade_time || "--"}</p>
                        <p>Last Signal: ${bot.last_signal || "--"}</p>
                        <p>Last Execution: ${bot.last_execution_time || "--"}</p>
                    </div>
                `;
            }).join("");
        }

        buildChart("equity-chart", "Equity", charts.equity_curve || [], "rgba(46, 204, 113, 1)");
        buildChart("balance-chart", "Balance", charts.balance_history || [], "rgba(33, 150, 243, 1)");
        buildChart("daily-profit-chart", "Daily Profit", charts.daily_profit || [], "rgba(255, 191, 102, 1)", "bar");
        buildChart("weekly-profit-chart", "Weekly Profit", charts.weekly_profit || [], "rgba(191, 122, 223, 1)", "bar");
        buildChart("monthly-profit-chart", "Monthly Profit", charts.monthly_profit || [], "rgba(255, 95, 87, 1)", "bar");
        buildChart("win-rate-chart", "Win Rate", charts.win_rate_history || [], "rgba(116, 224, 164, 1)");
        buildChart("drawdown-chart", "Drawdown", charts.drawdown_history || [], "rgba(255, 95, 87, 1)");

        renderTradeHistory(tradeHistory);
        renderNotificationCenter(notifications.items || []);
    } catch (err) {
        console.log(err);
    }
}

async function updateTradingJournal(){

    try {

        const response = await fetch(buildTradeHistoryUrl(1));
        const payload = await response.json();
        renderTradeHistory(payload);

    } catch (err) {
        console.log(err);
    }
}

function showNotification(message,type="success"){

    const container=document.getElementById("notification-container");

    if(!container) return;

    const note=document.createElement("div");

    note.className="notification "+type;

    note.innerHTML=message;

    container.appendChild(note);

    setTimeout(()=>{

        note.style.opacity="0";
        note.style.transform="translateX(400px)";

        setTimeout(()=>{

            note.remove();

        },500);

    },4000);

}

function addConsoleLog(message){

    const consoleBox=document.getElementById("bot-console");

    if(!consoleBox) return;

    const now=new Date();

    const time=now.toLocaleTimeString();

    const line=document.createElement("div");

    line.className="console-line";

    line.innerHTML=

    `<span class="console-time">${time}</span>${message}`;

    consoleBox.prepend(line);

    while(consoleBox.children.length>25){

        consoleBox.removeChild(consoleBox.lastChild);

    }

}

function refreshDashboard(){

    updateDashboard();

    updateMarket();

    updatePositions();

    updateSignals();

    updateBotLog();

    updateAssistantSummary();

    updateTradingJournal();

    updatePhase9Analytics();

}

document.addEventListener("DOMContentLoaded",()=>{

    const startButton = document.getElementById("start-bot-btn");
    const stopButton = document.getElementById("stop-bot-btn");
    const botSelector = document.getElementById("bot-selector");
    const mt5ConnectButton = document.getElementById("mt5-connect-btn");
    const mt5DisconnectButton = document.getElementById("mt5-disconnect-btn");
    const journalFilterButton = document.getElementById("trade-filter-btn");
    const tradeExportCsvButton = document.getElementById("trade-export-csv-btn");
    const tradeExportExcelButton = document.getElementById("trade-export-excel-btn");

    if (startButton) {
        startButton.addEventListener("click", async (event) => {
            event.preventDefault();
            const botId = document.getElementById("bot-selector")?.value || "";
            const response = await fetch("/api/bot/start", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
                body: JSON.stringify({ bot_id: botId }),
            });
            const data = await response.json();
            refreshDashboard();
            if (data.ok) {
                showNotification(data.message || "Bot started", "success");
            } else {
                showNotification(data.message || "Unable to start bot", "error");
            }
        });
    }

    if (stopButton) {
        stopButton.addEventListener("click", async (event) => {
            event.preventDefault();
            const botId = document.getElementById("bot-selector")?.value || "";
            const response = await fetch("/api/bot/stop", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
                body: JSON.stringify({ bot_id: botId }),
            });
            const data = await response.json();
            refreshDashboard();
            if (data.ok) {
                showNotification(data.message || "Bot stopped", "info");
            } else {
                showNotification(data.message || "Unable to stop bot", "error");
            }
        });
    }

    if (botSelector) {
        botSelector.addEventListener("change", async (event) => {
            await fetch("/api/bot/select", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
                body: JSON.stringify({ bot_id: event.target.value }),
            });
            refreshDashboard();
            showNotification("Bot selection updated", "success");
        });
    }

    if (mt5ConnectButton) {
        mt5ConnectButton.addEventListener("click", async (event) => {
            event.preventDefault();
            const login = document.getElementById("mt5-login")?.value || "";
            const password = document.getElementById("mt5-password")?.value || "";
            const server = document.getElementById("mt5-server")?.value || "";

            const response = await fetch("/api/mt5/connect", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
                body: JSON.stringify({ login, password, server }),
            });

            const data = await response.json();
            refreshDashboard();
            if (data.ok) {
                showNotification(data.message || "MT5 connected", "success");
            } else {
                showNotification(data.message || "MT5 connection failed", "error");
            }
        });
    }

    if (mt5DisconnectButton) {
        mt5DisconnectButton.addEventListener("click", async (event) => {
            event.preventDefault();
            const response = await fetch("/api/mt5/disconnect", {
                method: "POST",
                headers: { "X-CSRF-Token": csrfToken() },
            });
            const data = await response.json();
            refreshDashboard();
            if (data.ok) {
                showNotification(data.message || "MT5 disconnected", "info");
            } else {
                showNotification(data.message || "Unable to disconnect MT5", "error");
            }
        });
    }

    if (journalFilterButton) {
        journalFilterButton.addEventListener("click", async (event) => {
            event.preventDefault();
            await updateTradingJournal();
            showNotification("Trading journal filter applied", "info");
        });
    }

    if (tradeExportCsvButton) {
        tradeExportCsvButton.addEventListener("click", (event) => {
            event.preventDefault();
            window.location.href = buildTradeHistoryUrl(1).replace("/api/dashboard/trade-history?", "/api/dashboard/trade-history/export?format=csv&");
        });
    }

    if (tradeExportExcelButton) {
        tradeExportExcelButton.addEventListener("click", (event) => {
            event.preventDefault();
            window.location.href = buildTradeHistoryUrl(1).replace("/api/dashboard/trade-history?", "/api/dashboard/trade-history/export?format=excel&");
        });
    }

    refreshDashboard();
    addConsoleLog("✅ Dashboard initialized");
    showNotification("🟢 Welcome to Gwaro Capital");

    setInterval(refreshDashboard,5000);

    setTimeout(()=>{
        addConsoleLog("📊 Market feed listening");
    }, 1000);

    setTimeout(()=>{
        addConsoleLog("🔍 Signal engine monitoring");
    }, 2200);

});
function updateTicker(data){

    const ids = ["gold-price", "eurusd-price", "gbpusd-price", "btc-price", "nas-price"];
    ids.forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = "Disconnected";
        }
    });

    if(data.markets){

        data.markets.forEach(item=>{

            switch(item.symbol){

                case "XAUUSD.m":
                case "XAUUSD":
                case "XAUUSDz":

                    document.getElementById("gold-price").innerHTML=item.bid;
                    break;

                case "EURUSD.m":
                case "EURUSD":
                case "EURUSDz":

                    document.getElementById("eurusd-price").innerHTML=item.bid;
                    break;

                case "GBPUSD.m":
                case "GBPUSD":
                case "GBPUSDz":

                    document.getElementById("gbpusd-price").innerHTML=item.bid;
                    break;

                case "BTCUSD.m":
                case "BTCUSD":
                case "BTCUSDz":

                    document.getElementById("btc-price").innerHTML=item.bid;
                    break;

                case "NAS100.m":
                case "NAS100":
                case "USTEC":

                    document.getElementById("nas-price").innerHTML=item.bid;
                    break;

            }

        });

    }

}