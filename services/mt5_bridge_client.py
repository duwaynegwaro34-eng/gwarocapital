import os
import logging
import requests

logger = logging.getLogger("gwaro.mt5_bridge_client")


class MT5BridgeClient:
    def __init__(self, base_url=None, timeout=5.0):
        self.base_url = (base_url or os.getenv("MT5_BRIDGE_URL") or "").rstrip("/")
        self.timeout = float(timeout)

    def is_configured(self):
        return bool(self.base_url)

    def _url(self, path: str):
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _request(self, method, path, **kwargs):
        if not self.is_configured():
            raise ConnectionError("MT5 bridge URL not configured")
        try:
            resp = requests.request(method, self._url(path), timeout=self.timeout, **kwargs)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return resp.text
        except Exception as exc:
            logger.exception("Bridge request failed: %s %s", method, path)
            raise

    def connection_status(self):
        try:
            return self._request("GET", "/api/connection")
        except Exception:
            return {"connected": False, "status": "Offline", "reason": "MT5 Bridge unreachable"}

    def account_info(self):
        try:
            return self._request("GET", "/api/account")
        except Exception:
            return None

    def positions_get(self):
        try:
            return self._request("GET", "/api/positions") or []
        except Exception:
            return []

    def history_deals_get(self, start=None, end=None, limit=50):
        try:
            params = {"limit": limit}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            return self._request("GET", "/api/history", params=params) or []
        except Exception:
            return []

    def orders_get(self):
        try:
            return self._request("GET", "/api/orders") or []
        except Exception:
            return []

    def symbol_info_tick(self, symbol):
        try:
            return self._request("GET", f"/api/tick?symbol={symbol}")
        except Exception:
            return None

    def order_send(self, payload):
        try:
            return self._request("POST", "/api/order", json=payload)
        except Exception:
            return None

    def send_command(self, command, bot_id=None, bot_path=None, wait_for_ack=False):
        try:
            body = {"command": command, "bot_id": bot_id, "bot_path": bot_path, "wait_for_ack": bool(wait_for_ack)}
            return self._request("POST", "/api/command", json=body)
        except Exception as exc:
            logger.exception("Failed to send bridge command: %s", exc)
            return {"ok": False, "message": "Bridge unreachable"}
