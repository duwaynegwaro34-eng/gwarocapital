//==============================
// GWARO CAPITAL DASHBOARD
//==============================

async function updateDashboard(){

    try{

        const response = await fetch("/market_data");
        const data = await response.json();
        updateTicker(data);

        if(document.getElementById("balance"))
            document.getElementById("balance").innerHTML =
            "$"+Number(data.balance).toFixed(2);

        if(document.getElementById("equity"))
            document.getElementById("equity").innerHTML =
            "$"+Number(data.equity).toFixed(2);

        if(document.getElementById("profit"))
            document.getElementById("profit").innerHTML =
            "$"+Number(data.profit).toFixed(2);

        if(document.getElementById("status"))
            document.getElementById("status").innerHTML =
            data.status;

        if(document.getElementById("bot-status"))
            document.getElementById("bot-status").innerHTML =
            data.status;

    }

    catch(err){

        console.log(err);

    }

}

async function updateMarket(){

    try{

        const response = await fetch("/market_data");

        const data = await response.json();

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

        document.getElementById("market-data").innerHTML=html;

    }

    catch(err){

        console.log(err);

    }

}

async function updatePositions(){

    try{

        const response = await fetch("/positions");

        const positions = await response.json();

        let html="";

        positions.forEach(position=>{

            html+=`

            <tr>

                <td>${position.symbol}</td>

                <td>${position.type}</td>

                <td>${position.volume}</td>

                <td>$${position.profit}</td>

            </tr>

            `;

        });

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

        signals.forEach(signal=>{

            html+=`

            <div class="signal">

                <div class="signal-header">

                    <h3>${signal.symbol}</h3>

                    <span class="${signal.signal=="BUY"?"buy":"sell"}">

                    ${signal.signal}

                    </span>

                </div>

                <div class="signal-info">

                    <p>Entry : ${signal.entry}</p>

                    <p>SL : ${signal.sl}</p>

                    <p>TP : ${signal.tp}</p>

                    <p>Confidence : ${signal.confidence}%</p>

                </div>

            </div>

            `;

        });

        document.getElementById("signals").innerHTML=html;

    }

    catch(err){

        console.log(err);

    }

}

async function updateBotLog(){

    try{

        const response=await fetch("/bot_status");

        const data=await response.json();

        let html="";

        data.logs.forEach(log=>{

            html+=`

            <div class="log-item">

                ✅ ${log}

            </div>

            `;

        });

        document.getElementById("bot-log").innerHTML=html;

    }

    catch(err){

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

}

document.addEventListener("DOMContentLoaded",()=>{

    refreshDashboard();

    showNotification("🟢 Welcome to Gwaro Capital");

    setInterval(refreshDashboard,1000);
    showNotification("🤖 Bot Started","success");

setTimeout(()=>{

showNotification("📈 BUY Signal Detected","info");

},2000);

setTimeout(()=>{

showNotification("💰 Take Profit Hit","success");

},4000);

setTimeout(()=>{

showNotification("⚠ High Volatility","warning");

},6000);

addConsoleLog("✅ MT5 Connected");

setTimeout(()=>{

addConsoleLog("📊 Session Captured");

},1500);

setTimeout(()=>{

addConsoleLog("🔍 Scanning Market");

},3000);

setTimeout(()=>{

addConsoleLog("📈 BUY Signal Confirmed");

},4500);

setTimeout(()=>{

addConsoleLog("🚀 Trade Sent");

},6000);

setTimeout(()=>{

addConsoleLog("💰 Trade In Profit");

},7500);

});
function updateTicker(data){

    if(data.markets){

        data.markets.forEach(item=>{

            switch(item.symbol){

                case "XAUUSD.m":

                    document.getElementById("gold-price").innerHTML=item.bid;
                    break;

                case "EURUSD.m":

                    document.getElementById("eurusd-price").innerHTML=item.bid;
                    break;

                case "GBPUSD.m":

                    document.getElementById("gbpusd-price").innerHTML=item.bid;
                    break;

                case "BTCUSD.m":

                    document.getElementById("btc-price").innerHTML=item.bid;
                    break;

                case "NAS100.m":

                    document.getElementById("nas-price").innerHTML=item.bid;
                    break;

            }

        });

    }

}

.tradingview-widget-container{
    width:100%;
    height:100%;
}

#tradingview_chart{
    width:100%;
    height:650px;
}