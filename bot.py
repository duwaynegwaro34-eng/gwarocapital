trade_taken = False
trade_day = 0
from datetime import datetime

current_day = -1
trade_taken = False
session_captured = True

session_high = 0.0
session_low = 999999.0

# Avoid importing MetaTrader5 at module import time to keep web processes safe.
mt5 = None

def _get_mt5():
    global mt5
    if mt5 is not None:
        return mt5
    try:
        import MetaTrader5 as _mt5
        mt5 = _mt5
        return mt5
    except Exception:
        return None
import time
from datetime import datetime
TRADE_SYMBOL =  "XAUUSD.m"
TEST_MODE = True
LOT = 0.01
SESSION_START = 2
SESSION_END = 3
bullish_sweep = False
bearish_sweep = False
bullish_bos = False
bearish_bos = False
trade_taken = False
buy_order_block = 0.0
sell_order_block = 0.0
buy_fvg = 0.0
sell_fvg = 0.0

session_high = 0.0
session_low = 999999.0

session_captured = False
ACTIVE_EXECUTION_BOT = None
ACTIVE_EXECUTION_PATH = None
ACTIVE_EXECUTION_SYMBOL = None


def reset_trading_day():

    global current_day
    global trade_taken
    global session_captured
    global session_high
    global session_low

    today = datetime.now().day

    if today != current_day:

        current_day = today

        trade_taken = False
        session_captured = False

        session_high = 0.0
        session_low = 999999.0

        print("==============================")
        print("New Trading Day")
        print("==============================")

def capture_session():
    global session_high, session_low, session_captured
    now = datetime.now()

    m = _get_mt5()
    if m is None:
        return

    # Capture session between 02:00 and 03:00
    if now.hour == 1:
        rates = m.copy_rates_from_pos(TRADE_SYMBOL, m.TIMEFRAME_M5, 0, 12)
        if rates is None:
            return
        highs = [candle["high"] for candle in rates]
        lows = [candle["low"] for candle in rates]
        session_high = max(highs)
        session_low = min(lows)
        session_captured = True
        print(f"Session High: {session_high}")
        print(f"Session Low : {session_low}")

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        2
    )

    if rates is None:
        return

    candle = rates[-2]

    if session_high == 0 or candle["high"] > session_high:
        session_high = candle["high"]

    if candle["low"] < session_low:
        session_low = candle["low"]
        print(f"High: {session_high}")
        print(f"Low : {session_low}")

running = False


def configure_execution(bot_id, bot_path=None, chart_symbol=None):
    global ACTIVE_EXECUTION_BOT, ACTIVE_EXECUTION_PATH, ACTIVE_EXECUTION_SYMBOL
    ACTIVE_EXECUTION_BOT = bot_id
    ACTIVE_EXECUTION_PATH = bot_path
    ACTIVE_EXECUTION_SYMBOL = chart_symbol or TRADE_SYMBOL
    print(f"Configured execution for {bot_id} at {bot_path or 'unknown'} on {ACTIVE_EXECUTION_SYMBOL}")


def activate_execution(bot_id, bot_path=None, chart_symbol=None):
    configure_execution(bot_id, bot_path=bot_path, chart_symbol=chart_symbol)
    print(f"Activated expert {bot_id} on {ACTIVE_EXECUTION_SYMBOL}")


def deactivate_execution(bot_id, bot_path=None, chart_symbol=None):
    global ACTIVE_EXECUTION_BOT, ACTIVE_EXECUTION_PATH, ACTIVE_EXECUTION_SYMBOL
    ACTIVE_EXECUTION_BOT = None
    ACTIVE_EXECUTION_PATH = None
    ACTIVE_EXECUTION_SYMBOL = None
    print(f"Deactivated expert {bot_id}")


def detect_bos():

    global bullish_bos, bearish_bos

    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        3
    )

    if rates is None:
        return

    last = rates[-1]
    previous = rates[-2]

    # Bearish BOS after bullish sweep
    if bullish_sweep:

        if last["close"] < previous["low"]:
            bearish_bos = True
            print("Bearish BOS confirmed!")

    # Bullish BOS after bearish sweep
    if bearish_sweep:

        if last["close"] > previous["high"]:
            bullish_bos = True
            print("Bullish BOS confirmed!")
            
def detect_order_block():

    global buy_order_block, sell_order_block

    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        10
    )

    if rates is None:
        return

    # SELL setup
    if bearish_bos:

        for candle in reversed(rates):

            if candle["close"] > candle["open"]:

                sell_order_block = candle["high"]

                print(f"SELL Order Block: {sell_order_block}")

                return

    # BUY setup
    if bullish_bos:

        for candle in reversed(rates):

            if candle["close"] < candle["open"]:

                buy_order_block = candle["low"]

                print(f"BUY Order Block: {buy_order_block}")

                return

def wait_for_retest():

    global trade_taken

    if trade_taken:
        return

    m = _get_mt5()
    if m is None:
        return

    tick = m.symbol_info_tick(TRADE_SYMBOL)

    if tick is None:
        return

    # SELL Entry
    if bearish_bos and sell_order_block > 0:

        if tick.bid >= sell_order_block:

            print("SELL Retest Confirmed")
            place_sell()
            trade_taken = True

    # BUY Entry
    if bullish_bos and buy_order_block > 0:

        if tick.ask <= buy_order_block:

            print("BUY Retest Confirmed")
            place_buy()
            trade_taken = True

def execute_trade(direction):

    global trade_taken
    if trade_taken:
        return

    m = _get_mt5()
    if m is None:
        return

    tick = m.symbol_info_tick(TRADE_SYMBOL)

    if tick is None:
        return

    if direction == "BUY":
        price = tick.ask
        sl = session_low
        risk = price - sl
        tp = price + (risk * 3)
        order_type = m.ORDER_TYPE_BUY
    else:
        price = tick.bid
        sl = session_high
        risk = sl - price
        tp = price - (risk * 3)
        order_type = m.ORDER_TYPE_SELL

    request = {
        "action": m.TRADE_ACTION_DEAL,
        "symbol": TRADE_SYMBOL,
        "volume": LOT,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 714001,
        "comment": "Gwaro Capital",
        "type_time": m.ORDER_TIME_GTC,
        "type_filling": m.ORDER_FILLING_RETURN
    }

    result = m.order_send(request)
    print(result)
    try:
        retcode = getattr(result, "retcode", None)
    except Exception:
        retcode = None

    if retcode == getattr(m, "TRADE_RETCODE_DONE", None):
        trade_taken = True
        print("Trade Opened Successfully")

def capture_session():
    global session_high, session_low, session_captured

    now = datetime.now()

    if now.hour == SESSION_START and not session_captured:
        ...
        print(f"Session High: {session_high}")
        print(f"Session Low: {session_low}")

    if now.hour >= SESSION_END and not session_captured:
        session_captured = True
        print("Session captured successfully!")

def check_strategy():

    capture_session()

    if not session_captured:
        return

    detect_liquidity_sweep()
    detect_mss()
    detect_order_block()
    detect_fvg()
    wait_for_retest()
    
def detect_mss():

    global bullish_sweep
    global bearish_sweep
    global bullish_bos
    global bearish_bos

    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        5
    )

    if rates is None:
        return

    c1 = rates[-2]
    c2 = rates[-1]

    bullish_bos = False
    bearish_bos = False

    if bullish_sweep:

        if c2["close"] > c1["high"]:

            bullish_bos = True

            print("Bullish MSS")

    if bearish_sweep:

        if c2["close"] < c1["low"]:

            bearish_bos = True

            print("Bearish MSS")


def detect_order_block():

    global buy_order_block
    global sell_order_block

    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        20
    )

    if rates is None:
        return

    if bullish_bos:

        for candle in reversed(rates):

            if candle["close"] < candle["open"]:

                buy_order_block = candle["low"]

                print(f"BUY OB: {buy_order_block}")

                break

    if bearish_bos:

        for candle in reversed(rates):

            if candle["close"] > candle["open"]:

                sell_order_block = candle["high"]

                print(f"SELL OB: {sell_order_block}")

                break


def detect_fvg():

    global buy_fvg
    global sell_fvg

    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        5
    )

    if rates is None:
        return

    c1 = rates[-3]
    c2 = rates[-2]
    c3 = rates[-1]

    if bullish_bos:

        if c1["high"] < c3["low"]:

            buy_fvg = c3["low"]

            print(f"BUY FVG: {buy_fvg}")

    if bearish_bos:

        if c1["low"] > c3["high"]:

            sell_fvg = c3["high"]

            print(f"SELL FVG: {sell_fvg}")


def wait_for_retest():

    m = _get_mt5()
    if m is None:
        return

    tick = m.symbol_info_tick(TRADE_SYMBOL)

    if tick is None:
        return

    if bullish_bos:
        entry = buy_order_block if buy_order_block > 0 else buy_fvg
        if entry > 0 and tick.ask <= entry:
            print("BUY ENTRY")
            execute_trade("BUY")

    if bearish_bos:
        entry = sell_order_block if sell_order_block > 0 else sell_fvg
        if entry > 0 and tick.bid >= entry:
            print("SELL ENTRY")
            execute_trade("SELL")
    
def detect_liquidity_sweep():
    global bullish_sweep, bearish_sweep
    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        3
    )

    if rates is None:
        return

    c1 = rates[-2]
    c2 = rates[-1]

    bullish_sweep = False
    bearish_sweep = False

    # Sweep below session low
    if c2["low"] < session_low and c2["close"] > session_low:
        bullish_sweep = True
        print("Bullish liquidity sweep detected!")

    # Sweep above session high
    if c2["high"] > session_high and c2["close"] < session_high:
        bearish_sweep = True
        print("Bearish liquidity sweep detected!")
    
def confirm_entry():
    global bullish_sweep, bearish_sweep, trade_taken

    m = _get_mt5()
    if m is None:
        return

    rates = m.copy_rates_from_pos(
        TRADE_SYMBOL,
        m.TIMEFRAME_M5,
        0,
        5
    )

    if rates is None:
        return

    c1 = rates[-2]
    c2 = rates[-1]

    # BUY confirmation
    if bullish_sweep:
        if c2["close"] > c1["high"]:
            
            if trade_taken:
                return
            
            print("BUY confirmed")
            execute_trade("BUY")
            trade_taken = True
            bullish_sweep = False

    # SELL confirmation
    if bearish_sweep:
        if c2["close"] < c1["low"]:
            
            if trade_taken:
                return
            
            print("SELL confirmed")
            execute_trade("SELL")
            trade_taken = True
            bearish_sweep = False    

def detect_liquidity_sweep():
    global bullish_sweep, bearish_sweep

    rates = mt5.copy_rates_from_pos(
        TRADE_SYMBOL,
        mt5.TIMEFRAME_M5,
        0,
        3
    )

    if rates is None:
        return

    c1 = rates[-2]
    c2 = rates[-1]

    bullish_sweep = False
    bearish_sweep = False

    # Sweep below session low
    if c2["low"] < session_low and c2["close"] > session_low:
        bullish_sweep = True
        print("Bullish liquidity sweep detected!")

    # Sweep above session high
    if c2["high"] > session_high and c2["close"] < session_high:
        bearish_sweep = True
        print("Bearish liquidity sweep detected!")

def manage_trade():
    m = _get_mt5()
    if m is None:
        return

    positions = m.positions_get(symbol=TRADE_SYMBOL)
    if positions is None:
        return

    for position in positions:
        p_type = getattr(position, "type", None)
        if p_type == getattr(m, "POSITION_TYPE_BUY", None):
            profit = m.symbol_info_tick(TRADE_SYMBOL).bid - position.price_open
            if profit > 2:
                request = {
                    "action": m.TRADE_ACTION_SLTP,
                    "position": position.ticket,
                    "sl": position.price_open,
                    "tp": position.tp,
                }
                m.order_send(request)
        elif p_type == getattr(m, "POSITION_TYPE_SELL", None):
            profit = position.price_open - m.symbol_info_tick(TRADE_SYMBOL).ask
            if profit > 2:
                request = {
                    "action": m.TRADE_ACTION_SLTP,
                    "position": position.ticket,
                    "sl": position.price_open,
                    "tp": position.tp,
                }
                m.order_send(request)
  
def trailing_stop():
    m = _get_mt5()
    if m is None:
        return

    positions = m.positions_get(symbol=TRADE_SYMBOL)
    if positions is None:
        return

    tick = m.symbol_info_tick(TRADE_SYMBOL)

    for position in positions:
        if getattr(position, "type", None) == getattr(m, "POSITION_TYPE_BUY", None):
            new_sl = tick.bid - 1.0
            if new_sl > position.sl:
                request = {
                    "action": m.TRADE_ACTION_SLTP,
                    "position": position.ticket,
                    "sl": new_sl,
                    "tp": position.tp,
                }
                m.order_send(request)
        elif getattr(position, "type", None) == getattr(m, "POSITION_TYPE_SELL", None):
            new_sl = tick.ask + 1.0
            if position.sl == 0 or new_sl < position.sl:
                request = {
                    "action": m.TRADE_ACTION_SLTP,
                    "position": position.ticket,
                    "sl": new_sl,
                    "tp": position.tp,
                }
                m.order_send(request)
    
def start():
    global running
    running = True

    print("Loading Gwaro Capital EA")
    m = _get_mt5()
    if m is None:
        print("MetaTrader5 module not available. Bot cannot start in this environment.")
        return

    while running:
        account = m.account_info()
        if account:
            try:
                bal = getattr(account, "balance", None)
                print(f"Balance: {bal}")
            except Exception:
                pass

        capture_session()
        check_strategy()
        manage_trade()
        trailing_stop()

        time.sleep(5)

    try:
        m.shutdown()
    except Exception:
        pass
    print("Bot stopped.")

def stop():
    global running
    running = False