from datetime import datetime, timezone
import threading
from config import settings as app_settings
from services.mt5_bridge_client import MT5BridgeClient


class MT5Manager:
    """
    Adapter that provides the same high-level methods but routes calls
    to a remote MT5 Bridge over HTTP when configured. If no bridge URL is
    configured, methods behave as if MT5 is unavailable (bridge offline).
    """
    def __init__(self, bridge_url=None):
        self._lock = threading.RLock()
        resolved_url = bridge_url or app_settings.mt5_bridge_url or ""
        if not resolved_url:
            host = app_settings.mt5_bridge_host or ""
            port = app_settings.mt5_bridge_port or "5001"
            if host and port:
                resolved_url = f"http://{host}:{port}"
        self._bridge = MT5BridgeClient(
            base_url=resolved_url,
            timeout=app_settings.mt5_bridge_timeout_seconds,
            api_key=app_settings.mt5_bridge_api_key,
        )

    def connection_status(self):
        try:
            status = self._bridge.connection_status()
            return {
                "installed": True,
                "running": bool(status.get("connected")),
                "connected": bool(status.get("connected")),
                "status": status.get("status") or ("Connected" if status.get("connected") else "Disconnected"),
                "account_login": status.get("account_login"),
                "server": status.get("server"),
                "connection_time": status.get("connection_time") or "--",
                "last_error": status.get("reason") or None,
            }
        except Exception:
            return {
                "installed": False,
                "running": False,
                "connected": False,
                "status": "Offline",
                "account_login": None,
                "server": "",
                "connection_time": "--",
                "last_error": "MT5 Bridge unreachable",
            }

    def initialize_client(self):
        # Health-check the bridge before attempting to connect.
        if not self._bridge.is_configured():
            return False
        try:
            health = self._bridge.health()
            return bool(health.get("ok"))
        except Exception:
            return False

    def shutdown_client(self):
        # No local shutdown required for bridge
        return True

    def connect(self, login=None, password=None, server=None, session_id=None):
        try:
            return self._bridge.connect(login=login, password=password, server=server, session_id=session_id)
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": str(exc)}

    def disconnect(self, session_id=None):
        try:
            return self._bridge.disconnect(session_id=session_id)
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": str(exc)}

    def account_info(self):
        try:
            return self._bridge.account_info()
        except Exception:
            return None

    def positions_get(self):
        try:
            return self._bridge.positions_get()
        except Exception:
            return []

    def history_deals_get(self, start=None, end=None, limit=50):
        try:
            return self._bridge.history_deals_get(start=start, end=end, limit=limit)
        except Exception:
            return []

    def orders_get(self):
        try:
            return self._bridge.orders_get()
        except Exception:
            return []

    def symbol_info_tick(self, symbol):
        try:
            return self._bridge.symbol_info_tick(symbol)
        except Exception:
            return None

    def order_send(self, payload):
        try:
            return self._bridge.order_send(payload)
        except Exception:
            return None
    def start_bot(self, bot_id=None, session_id=None):
        try:
            return self._bridge.send_command("start", bot_id or "gwarodollarprinter", session_id=session_id)
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": str(exc)}

    def stop_bot(self, bot_id=None, session_id=None):
        try:
            return self._bridge.send_command("stop", bot_id or "gwarodollarprinter", session_id=session_id)
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": str(exc)}

# Default manager uses environment variable MT5_BRIDGE_URL if present
mt5_manager = MT5Manager(bridge_url=None)
