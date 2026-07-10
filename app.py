from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
# import bot
import threading
import time

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gwaro.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    mt5_account = db.Column(db.String(50))
    mt5_server = db.Column(db.String(100))
    mt5_name = db.Column(db.String(100))
    mt5_connected = db.Column(db.Boolean, default=False)


bot_running = False


def get_market_data():
    data = []

    if mt5.initialize():

        wanted = ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"]

        for symbol in mt5.symbols_get():

            for name in wanted:

                if symbol.name.startswith(name):

                    mt5.symbol_select(symbol.name, True)

                    tick = mt5.symbol_info_tick(symbol.name)

                    if tick:
                        data.append({
                            "symbol": symbol.name,
                            "bid": round(tick.bid, 5),
                            "ask": round(tick.ask, 5)
                        })

        mt5.shutdown()

    return data


def generate_signals():

    signals = []

    if mt5.initialize():

        symbols = ["XAUUSD.m", "EURUSD.m", "GBPUSD.m", "BTCUSD.m"]

        for symbol in symbols:

            tick = mt5.symbol_info_tick(symbol)

            if tick:

                signal = "BUY" if tick.bid > tick.ask - 1 else "SELL"

                signals.append({
                    "symbol": symbol,
                    "signal": signal,
                    "entry": round(tick.ask, 5),
                    "sl": round(tick.ask - 1, 5),
                    "tp": round(tick.ask + 2, 5),
                    "confidence": 90
                })

        mt5.shutdown()

    return signals
def bot_loop():
    global bot_running

    while bot_running:

        print("Bot is running...")

        # EA trading logic goes here

        import time
        time.sleep(5)
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/positions")
def positions():

    positions = mt5.positions_get()

    data=[]

    if positions:

        for p in positions:

            data.append({

                "symbol":p.symbol,

                "type":"BUY" if p.type==0 else "SELL",

                "volume":p.volume,

                "profit":round(p.profit,2)

            })

    return jsonify(data)

@app.route("/signals")
def signals():

    return jsonify([

        {

            "symbol":"XAUUSD",

            "signal":"BUY",

            "entry":0,

            "sl":0,

            "tp":0,

            "confidence":95

        }

    ])
    
@app.route("/bot_status")
def bot_status():

    return jsonify({

        "logs":[

            "MT5 Connected",

            "Bot Running",

            "Monitoring Session",

            "Waiting For Trade"

        ]

    })
    
    

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        user = User(
            username=request.form["username"],
            email=request.form["email"],
            password=request.form["password"]
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/mt5", methods=["GET", "POST"])
def mt5_page():

    if request.method == "POST":

        user = User.query.first()

        if user:

            user.mt5_account = request.form["account"]
            user.mt5_server = request.form["server"]
            user.mt5_name = request.form["name"]
            user.mt5_connected = True

            db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("mt5.html")
@app.route("/test_mt5")
def test_mt5():

    if not mt5.initialize():
        return "❌ Failed to connect to MetaTrader 5."

    account = mt5.account_info()

    if account is None:
        mt5.shutdown()
        return "❌ No MT5 account is logged in."

    data = f"""
    <h2>MT5 Connected</h2>
    <p><b>Account:</b> {account.login}</p>
    <p><b>Server:</b> {account.server}</p>
    <p><b>Balance:</b> {account.balance}</p>
    <p><b>Equity:</b> {account.equity}</p>
    <p><b>Profit:</b> {account.profit}</p>
    <p><b>Free Margin:</b> {account.margin_free}</p>
    """

    mt5.shutdown()

    return data


@app.route("/dashboard")
def dashboard():

    user = User.query.first()

    mt5_data = None

    if mt5.initialize():

        account = mt5.account_info()

        if account:

            mt5_data = {
                "status": "Connected",
                "account": account.login,
                "server": account.server,
                "balance": account.balance,
                "equity": account.equity,
                "profit": account.profit,
                "margin": account.margin_free
            }

        mt5.shutdown()

    market = get_market_data()
    signals = generate_signals()

    return render_template(
        "dashboard.html",
        user=user,
        mt5=mt5_data,
        market=market,
        signals=signals,
        bot_running=bot_running
    )


@app.route("/start_bot")
def start_bot():

    global bot_running
    global bot_thread

    if not bot_running:
        bot_running = True

        bot_thread = threading.Thread(target=bot.start)
        bot_thread.daemon = True
        bot_thread.start()

    return redirect(url_for("dashboard"))

@app.route("/stop_bot")
def stop_bot():

    global bot_running

    bot_running = False

    return redirect(url_for("dashboard"))


if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0",
port=5000, debug=True)