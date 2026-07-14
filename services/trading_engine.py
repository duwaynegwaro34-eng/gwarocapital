from datetime import datetime, timezone
import os
import threading
import time

from mt5_manager import mt5
from config import settings as app_settings


class TradingEngine:
    def __init__(self, bot_module, mt5_manager, event_callback=None, poll_interval=2.0):
        self._bot_module = bot_module
        self._mt5_manager = mt5_manager
        self._event_callback = event_callback
        self._poll_interval = poll_interval

        self._lock = threading.RLock()
        self._running = False
        self._error = ""
        self._active_bot_id = None
        self._thread = None
        self._start_time = None
        self._last_execution = None
        self._last_heartbeat = None
        self._known_positions = {}
        self._bot_registry = {}
        self._chart_symbol = getattr(app_settings, "mt5_chart_symbol", None) or os.getenv("MT5_CHART_SYMBOL", "XAUUSD")
        self._bot_registry = {}
        self._chart_symbol = getattr(app_settings, "mt5_chart_symbol", None) or os.getenv("MT5_CHART_SYMBOL", "XAUUSD")

    def set_bot_registry(self, registry):
        with self._lock:
            self._bot_registry = dict(registry or {})

    def start(self, bot_id):
        with self._lock:
            if self._running:
                return False, "Bot already running"

            self._running = True
            self._error = ""
            self._active_bot_id = bot_id
            self._start_time = datetime.now(timezone.utc)
            self._last_execution = self._start_time
            self._last_heartbeat = self._start_time
            self._known_positions = {}

        self._activate_bot(bot_id)

        with self._lock:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

        return True, "Bot started"

    def stop(self):
        with self._lock:
            if not self._running:
                return False, "Bot already stopped"
            self._running = False
            self._last_heartbeat = datetime.now(timezone.utc)
            active_bot_id = self._active_bot_id

        try:
            if hasattr(self._bot_module, "stop"):
                self._bot_module.stop()
        except Exception:
            pass

        self._deactivate_bot(active_bot_id)

        with self._lock:
            self._active_bot_id = None

        return True, "Bot stopped"

    def heartbeat(self):
        with self._lock:
            self._last_heartbeat = datetime.now(timezone.utc)
            return self._last_heartbeat

    def status(self):
        with self._lock:
            running = self._running
            start_time = self._start_time.isoformat() if self._start_time else "--"
            last_execution = self._last_execution.isoformat() if self._last_execution else "--"
            error = self._error
            last_heartbeat = self._last_heartbeat.isoformat() if self._last_heartbeat else None

        return {
            "running": running,
            "error": error,
            "start_time": start_time,
            "last_execution": last_execution,
            "last_heartbeat": last_heartbeat,
            "uptime": self._uptime(),
        }

    def _run(self):
        if not self._mt5_manager.initialize_client():
            self._set_error("MT5 connection unavailable.")
            self._emit("Errors", "MT5 connection unavailable")
            return

        try:
            while True:
                with self._lock:
                    if not self._running:
                        break
                    self._last_heartbeat = datetime.now(timezone.utc)
                    bot_id = self._active_bot_id

                try:
                    if mt5 is None or mt5.account_info() is None:
                        raise RuntimeError("No authenticated MT5 account is active")

                    self._run_bot_cycle(bot_id)
                    self._track_position_events()

                    with self._lock:
                        self._last_execution = datetime.now(timezone.utc)
                        self._last_heartbeat = datetime.now(timezone.utc)
                        self._error = ""
                except Exception as exc:
                    self._set_error(str(exc))
                    self._emit("Errors", f"Engine runtime error: {exc}")
                    break

                time.sleep(self._poll_interval)
        finally:
            self._mt5_manager.shutdown_client()
            with self._lock:
                self._running = False

    def _run_bot_cycle(self, bot_id):
        cycle_functions = [
            "reset_trading_day",
            "capture_session",
            "check_strategy",
            "manage_trade",
            "trailing_stop",
        ]

        for function_name in cycle_functions:
            function_obj = getattr(self._bot_module, function_name, None)
            if callable(function_obj):
                function_obj()

    def _resolve_bot_config(self, bot_id):
        with self._lock:
            bot_config = self._bot_registry.get(bot_id)

        if isinstance(bot_config, dict):
            return {
                "id": bot_config.get("id") or bot_id,
                "name": bot_config.get("name") or bot_id,
                "path": bot_config.get("path"),
            }

        return {"id": bot_id, "name": bot_id, "path": None}

    def _activate_bot(self, bot_id):
        bot_config = self._resolve_bot_config(bot_id)
        chart_symbol = self._chart_symbol
        bot_path = bot_config.get("path")

        for method_name in ("configure_execution", "activate_execution", "activate_bot", "attach_expert", "attach_bot"):
            method = getattr(self._bot_module, method_name, None)
            if not callable(method):
                continue
            try:
                method(bot_id, bot_path, chart_symbol=chart_symbol)
            except TypeError:
                method(bot_id, bot_path)
            break

        self._emit(
            "Bot Activated",
            f"Bot activated: {bot_config.get('name', bot_id)}",
            {
                "bot_id": bot_id,
                "bot_name": bot_config.get("name", bot_id),
                "bot_path": bot_path,
                "chart_symbol": chart_symbol,
            },
        )

    def _deactivate_bot(self, bot_id):
        if not bot_id:
            return

        bot_config = self._resolve_bot_config(bot_id)
        chart_symbol = self._chart_symbol
        bot_path = bot_config.get("path")

        for method_name in ("deactivate_execution", "deactivate_bot", "detach_expert", "detach_bot"):
            method = getattr(self._bot_module, method_name, None)
            if not callable(method):
                continue
            try:
                method(bot_id, bot_path, chart_symbol=chart_symbol)
            except TypeError:
                method(bot_id, bot_path)
            break

        self._emit(
            "Bot Deactivated",
            f"Bot deactivated: {bot_config.get('name', bot_id)}",
            {
                "bot_id": bot_id,
                "bot_name": bot_config.get("name", bot_id),
                "bot_path": bot_path,
                "chart_symbol": chart_symbol,
            },
        )

    def _track_position_events(self):
        if mt5 is None:
            return

        positions = mt5.positions_get() or []
        current_positions = {}

        for position in positions:
            ticket = getattr(position, "ticket", None)
            if ticket is None:
                continue
            current_positions[ticket] = {
                "symbol": getattr(position, "symbol", ""),
                "type": "BUY" if getattr(position, "type", 1) == 0 else "SELL",
                "volume": float(getattr(position, "volume", 0.0) or 0.0),
                "profit": float(getattr(position, "profit", 0.0) or 0.0),
            }

        opened = set(current_positions.keys()) - set(self._known_positions.keys())
        closed = set(self._known_positions.keys()) - set(current_positions.keys())

        for ticket in opened:
            data = current_positions[ticket]
            self._emit(
                "Trade Opened",
                f"Trade Opened: #{ticket} {data['symbol']} {data['type']} lot {data['volume']}",
                {
                    "ticket": str(ticket),
                    "symbol": data["symbol"],
                    "position_type": data["type"],
                    "volume": data["volume"],
                    "profit": data["profit"],
                    "bot": self._active_bot_id,
                },
            )

        for ticket in closed:
            data = self._known_positions[ticket]
            self._emit(
                "Trade Closed",
                f"Trade Closed: #{ticket} {data['symbol']} P/L {data['profit']:.2f}",
                {
                    "ticket": str(ticket),
                    "symbol": data["symbol"],
                    "position_type": data["type"],
                    "volume": data["volume"],
                    "profit": data["profit"],
                    "bot": self._active_bot_id,
                },
            )

        self._known_positions = current_positions

    def _set_error(self, error_message):
        with self._lock:
            self._error = error_message
            self._running = False

    def _uptime(self):
        with self._lock:
            if not self._running or self._start_time is None:
                return "00:00:00"
            delta = datetime.now(timezone.utc) - self._start_time

        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _emit(self, event_type, message, data=None):
        if not callable(self._event_callback):
            return
        payload = {
            "type": event_type,
            "message": message,
            "time": datetime.now(timezone.utc).isoformat(),
        }
        if data and isinstance(data, dict):
            payload.update(data)
        self._event_callback(payload)
