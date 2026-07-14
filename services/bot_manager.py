from dataclasses import dataclass
from datetime import datetime, timezone
import os
import threading
from mt5_manager import mt5_manager
from services.trading_engine import TradingEngine
from services.mt5_bridge import MT5Bridge
from config import settings as app_settings

DEFAULT_MT5_EXPERTS_PATH = app_settings.mt5_experts_path

# Single bot configuration - Gwaro Dollar Printer only
SINGLE_BOT_ID = "gwarodollarprinter"
SINGLE_BOT_NAME = "Gwaro Dollar Printer"
SINGLE_BOT_SYMBOL = "XAUUSD"


@dataclass(frozen=True)
class BotDefinition:
    bot_id: str
    name: str
    symbol: str
    path: str | None = None


class BotManager:
    def __init__(self, bot_module):
        self.bot_module = bot_module
        self._lock = threading.RLock()
        self._last_signal = "No signal yet"
        self._last_trade_result = "No trades yet"
        self._last_error = ""
        self._last_start_time = None
        self._last_stop_time = None
        self._last_restart_time = None
        self._last_heartbeat = None
        self._restart_count = 0
        self._active_bot = SINGLE_BOT_ID
        self._mt5_account = None
        self._running = False
        self._activity_log = []
        self._bot = BotDefinition(SINGLE_BOT_ID, SINGLE_BOT_NAME, SINGLE_BOT_SYMBOL)
        self._engine = TradingEngine(self.bot_module, mt5_manager, event_callback=self._record_activity)
        self._bridge = MT5Bridge(mt5_manager=mt5_manager)

    def discover_available_bots(self, experts_dir=None):
        """Discover bots from an experts directory when available, otherwise fall back to the single Gwaro bot."""
        discovered = []
        search_root = experts_dir or DEFAULT_MT5_EXPERTS_PATH
        if search_root and os.path.isdir(search_root):
            for current_root, dirnames, filenames in os.walk(search_root):
                dirnames.sort()
                for filename in sorted(filenames):
                    name_lower = filename.lower()
                    if not (name_lower.endswith(".ex5") or name_lower.endswith(".ex4") or name_lower.endswith(".mq5")):
                        continue
                    bot_id = os.path.splitext(filename)[0].lower()
                    if bot_id in {item["id"] for item in discovered}:
                        continue
                    discovered.append({
                        "id": bot_id,
                        "name": os.path.splitext(filename)[0],
                        "symbol": SINGLE_BOT_SYMBOL,
                    })

        if discovered:
            return discovered

        return [{"id": SINGLE_BOT_ID, "name": SINGLE_BOT_NAME, "symbol": SINGLE_BOT_SYMBOL}]

    def available_bots(self):
        """Return the currently available bot list."""
        return self.discover_available_bots()

    def set_active_bot(self, bot_id):
        """Select the current bot for compatibility with the bot-control UI and tests."""
        if self._running or self._engine.status()["running"]:
            return False, "Stop the running bot before switching"

        resolved_id = (bot_id or SINGLE_BOT_ID).strip()
        if not resolved_id:
            resolved_id = SINGLE_BOT_ID

        self._active_bot = resolved_id
        self._record_activity({
            "type": "Bot Selected",
            "message": f"Bot selected: {resolved_id}",
            "time": datetime.now(timezone.utc).isoformat(),
        })
        return True, "Bot selected"

    def _resolve_mt5_account(self, mt5_account=None):
        if mt5_account:
            return str(mt5_account)
        status = mt5_manager.connection_status()
        account_login = status.get("account_login")
        if account_login:
            return str(account_login)
        return None

    def _authorize_start(self, user=None, mt5_account=None):
        if user is None:
            return True, ""

        if not getattr(user, "mt5_account", None):
            return False, "No MT5 account linked for licensing"

        resolved_account = self._resolve_mt5_account(mt5_account)
        if not resolved_account:
            return False, "No MT5 account linked for licensing"

        if str(getattr(user, "mt5_account", "")) != str(resolved_account):
            return False, "MT5 account does not match the licensed account"

        return True, "Authorized"

    def _send_control_command(self, command, banner, bot_id=None):
        bridge_ok, bridge_message = self._bridge.send_command(
            command,
            bot_id or SINGLE_BOT_ID,
            wait_for_ack=True,
            timeout=5.0,
            poll_interval=0.2,
        )
        if not bridge_ok:
            self._record_activity({
                "type": "Errors",
                "message": bridge_message or f"MT5 EA did not acknowledge {command}",
                "time": datetime.now(timezone.utc).isoformat(),
            })
            self._last_signal = f"{command} not acknowledged"
            self._last_trade_result = "No active trade"
            return False, bridge_message or f"MT5 EA did not acknowledge {command}"

        self._record_activity({
            "type": "Bot Control",
            "message": banner,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        return True, banner

    def close_all_trades(self, bot_id=None):
        return self._send_control_command(
            "close_all",
            f"Close all trades requested for {SINGLE_BOT_NAME}",
            bot_id=bot_id,
        )

    def break_even(self, bot_id=None):
        return self._send_control_command(
            "break_even",
            f"Break-even requested for {SINGLE_BOT_NAME}",
            bot_id=bot_id,
        )

    def refresh_state(self):
        self._bridge.sync_from_terminal()
        return True, "Bridge status refreshed"

    def start(self, bot_id=None, user=None, mt5_account=None, enforce_security=False):
        import logging
        logger = logging.getLogger("gwaro.bot_manager")
        logger.info("BotManager.start called for single bot architecture")

        with self._lock:
            if self._running or self._engine.status()["running"]:
                return False, "Bot already running"

            resolved_bot_id = (bot_id or self._active_bot or SINGLE_BOT_ID).strip() or SINGLE_BOT_ID
            self._active_bot = resolved_bot_id

            if enforce_security:
                ok, message = self._authorize_start(user=user, mt5_account=mt5_account)
                if not ok:
                    self._record_activity({
                        "type": "Errors",
                        "message": message or "Bot start blocked by security validation",
                        "time": datetime.now(timezone.utc).isoformat(),
                    })
                    self._last_signal = "Security blocked"
                    self._last_trade_result = "No active trade"
                    return False, message or "Bot start blocked by security validation"

            mt5_status = mt5_manager.connection_status()
            if not mt5_status.get("connected"):
                self._record_activity({
                    "type": "Info",
                    "message": "Starting bot through bridge mode while MT5 is disconnected",
                    "time": datetime.now(timezone.utc).isoformat(),
                })

            self._mt5_account = self._resolve_mt5_account(mt5_account) or self._mt5_account

            bridge_ok, bridge_message = self._bridge.send_command(
                "start",
                resolved_bot_id,
                bot_path=None,
                wait_for_ack=True,
                timeout=5.0,
                poll_interval=0.2,
            )
            logger.info("Bridge send_command result: %s %s", bridge_ok, bridge_message)
            if not bridge_ok:
                self._record_activity({
                    "type": "Errors",
                    "message": bridge_message or "MT5 EA did not acknowledge START",
                    "time": datetime.now(timezone.utc).isoformat(),
                })
                self._last_signal = "MT5 start not acknowledged"
                self._last_trade_result = "No active trade"

            ok, message = self._engine.start(resolved_bot_id)
            if not ok:
                return False, message

            self._running = True
            self._last_start_time = datetime.now(timezone.utc)
            self._last_stop_time = None
            self._last_error = ""
            self._last_signal = "Engine started"
            self._last_trade_result = "Awaiting first trade"
            self._last_heartbeat = datetime.now(timezone.utc)
            self._record_activity({
                "type": "Bot Started",
                "message": f"Bot Started: {resolved_bot_id} on {SINGLE_BOT_SYMBOL}",
                "time": datetime.now(timezone.utc).isoformat(),
            })

        return True, "Bot started"

    def stop(self, bot_id=None):
        import logging
        logger = logging.getLogger("gwaro.bot_manager")
        logger.info("BotManager.stop called")

        with self._lock:
            requested_bot_id = (bot_id or self._active_bot or SINGLE_BOT_ID).strip() or SINGLE_BOT_ID
            if self._active_bot and str(self._active_bot) != str(requested_bot_id):
                return False, "Selected bot does not match the currently active bot"

            self._active_bot = requested_bot_id

            bridge_ok, bridge_message = self._bridge.send_command(
                "stop",
                requested_bot_id,
                wait_for_ack=True,
                timeout=5.0,
                poll_interval=0.2,
            )
            logger.info("Bridge send_command result: %s %s", bridge_ok, bridge_message)
            if not bridge_ok:
                self._record_activity({
                    "type": "Errors",
                    "message": bridge_message or "MT5 EA did not acknowledge STOP",
                    "time": datetime.now(timezone.utc).isoformat(),
                })
                self._last_signal = "MT5 stop not acknowledged"
                self._last_trade_result = "No active trade"

            ok, message = self._engine.stop()
            if not ok:
                return False, message

            self._running = False
            self._last_stop_time = datetime.now(timezone.utc)
            self._last_signal = "Engine stopped"
            self._last_trade_result = "No active trade"
            self._last_heartbeat = datetime.now(timezone.utc)
            self._record_activity({
                "type": "Bot Stopped",
                "message": f"Bot Stopped: {requested_bot_id}",
                "time": datetime.now(timezone.utc).isoformat(),
            })

        return True, "Bot stopped"

    def restart(self, bot_id=None, user=None, mt5_account=None, enforce_security=False):
        with self._lock:
            if self._running or self._engine.status()["running"]:
                self.stop()

            self._restart_count += 1
            self._last_restart_time = datetime.now(timezone.utc)
            self._record_activity({
                "type": "Bot Restarted",
                "message": f"Bot Restarted: {SINGLE_BOT_NAME}",
                "time": datetime.now(timezone.utc).isoformat(),
            })

        return self.start(user=user, mt5_account=mt5_account, enforce_security=enforce_security)

    def heartbeat(self):
        with self._lock:
            self._last_heartbeat = datetime.now(timezone.utc)
            return self._last_heartbeat

    def _uptime(self):
        return self._engine.status()["uptime"]

    def activity_log(self, limit=30):
        with self._lock:
            return list(self._activity_log[:limit])

    def _record_activity(self, event):
        with self._lock:
            self._activity_log.insert(0, event)
            self._activity_log = self._activity_log[:100]
            self._last_heartbeat = datetime.now(timezone.utc)

            event_type = event.get("type", "")
            message = event.get("message", "")

            if event_type == "Trade Opened":
                self._last_signal = "Trade opened"
                self._last_trade_result = message
            elif event_type == "Trade Closed":
                self._last_signal = "Trade closed"
                self._last_trade_result = message
            elif event_type == "Errors":
                self._last_signal = "Engine error"
                self._last_trade_result = message
                self._last_error = message
            elif event_type == "Bot Started":
                self._last_signal = "Engine started"
            elif event_type == "Bot Stopped":
                self._last_signal = "Engine stopped"

    def status(self):
        engine_state = self._engine.status()
        with self._lock:
            running = self._running or engine_state["running"]
            status = "Error" if engine_state["error"] else ("Running" if running else "Stopped")
            mt5_state = mt5_manager.connection_status()
            bridge_state = self._bridge.get_status()
            bridge_running = bridge_state.get("state") == "running" or running
            current_bot_id = self._active_bot or SINGLE_BOT_ID
            current_bot_name = SINGLE_BOT_NAME if current_bot_id == SINGLE_BOT_ID else current_bot_id
            return {
                "current_bot_id": current_bot_id,
                "current_bot": current_bot_name,
                "symbol": SINGLE_BOT_SYMBOL,
                "running": bridge_running,
                "status": "Running" if bridge_running else status,
                "start_time": engine_state["start_time"],
                "last_start_time": self._last_start_time.isoformat() if self._last_start_time else None,
                "last_stop_time": self._last_stop_time.isoformat() if self._last_stop_time else None,
                "last_restart_time": self._last_restart_time.isoformat() if self._last_restart_time else None,
                "uptime": engine_state["uptime"],
                "engine_uptime": engine_state["uptime"],
                "last_execution": engine_state["last_execution"],
                "last_signal": bridge_state.get("last_signal") or self._last_signal,
                "last_trade_result": bridge_state.get("last_trade_result") or self._last_trade_result,
                "last_trade": bridge_state.get("last_trade_result") or self._last_trade_result,
                "last_error": bridge_state.get("last_error") or self._last_error,
                "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
                "restart_count": self._restart_count,
                "mt5_account": self._mt5_account,
                "mt5_connection_status": mt5_state.get("status", "Disconnected"),
                "mt5_connected": bool(mt5_state.get("connected")),
                "balance": bridge_state.get("balance"),
                "equity": bridge_state.get("equity"),
                "profit": bridge_state.get("profit"),
                "open_trades": bridge_state.get("open_trades"),
                "error": engine_state["error"],
                "activity_log": self.activity_log(),
            }
