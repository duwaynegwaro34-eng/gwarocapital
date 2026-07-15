import os
import logging

try:
    import requests
except ImportError:  # pragma: no cover - non-standard env fallback
    requests = None

logger = logging.getLogger("gwaro.mt5_bridge_client")


class MT5BridgeClient:
    def __init__(self, base_url=None, timeout=5.0, api_key=None):
        self.timeout = float(timeout)
        self.api_key = (api_key or os.getenv("MT5_BRIDGE_API_KEY") or "").strip()
        configured = (base_url or os.getenv("MT5_BRIDGE_URL") or "").strip().rstrip("/")
        if configured:
            self.base_url = configured
        else:
            host = (os.getenv("MT5_BRIDGE_HOST") or "").strip()
            port = (os.getenv("MT5_BRIDGE_PORT") or "5001").strip()
            if host and port:
                self.base_url = f"http://{host}:{port}"
            else:
                self.base_url = ""

    def is_configured(self):
        return bool(self.base_url)

    def health(self):
        if not self.is_configured():
            return {"ok": False, "status": "misconfigured", "message": "MT5 bridge URL is not configured", "base_url": self.base_url}
        try:
            payload = self._request("GET", "/health")
            if isinstance(payload, dict):
                return {"ok": bool(payload.get("ok", True)), "status": payload.get("status", "ok"), "message": payload.get("message") or "Bridge responded", "base_url": self.base_url, "details": payload}
            return {"ok": True, "status": "ok", "message": "Bridge responded", "base_url": self.base_url, "details": payload}
        except Exception as exc:
            if requests is not None and hasattr(requests, "RequestException") and isinstance(exc, requests.RequestException):
                return {"ok": False, "status": "unreachable", "message": f"Bridge unreachable at {self.base_url}: {exc}", "base_url": self.base_url, "details": {"error": str(exc)}}
            return {"ok": False, "status": "offline", "message": f"Bridge request failed: {exc}", "base_url": self.base_url, "details": {"error": str(exc)}}

    def connect(self, login=None, password=None, server=None, session_id=None):
        try:
            payload = {"login": login, "password": password, "server": server, "session_id": session_id}
            return self._request("POST", "/connect", json=payload)
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": f"Bridge connect failed: {exc}"}

    def disconnect(self, session_id=None):
        try:
            payload = {"session_id": session_id} if session_id else {}
            return self._request("POST", "/disconnect", json=payload)
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": f"Bridge disconnect failed: {exc}"}

    def _url(self, path: str):
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self):
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(self, method, path, **kwargs):
        if not self.is_configured():
            raise ConnectionError("MT5 bridge URL not configured")
        headers = kwargs.pop("headers", {})
        headers = {**self._headers(), **headers}
        attempts = kwargs.pop("attempts", 3)
        if requests is None:
            raise RuntimeError("requests package is required for MT5 bridge client")
        for attempt in range(1, attempts + 1):
            try:
                resp = requests.request(method, self._url(path), timeout=self.timeout, headers=headers, **kwargs)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    return resp.text
            except Exception as exc:
                if attempt >= attempts:
                    logger.exception("Bridge request failed: %s %s", method, path)
                    raise
                logger.warning("Bridge request attempt %s/%s failed for %s %s: %s", attempt, attempts, method, path, exc)
        raise RuntimeError("Bridge request exhausted")

    def connection_status(self):
        try:
            return self._request("GET", "/health")
        except Exception as exc:
            return {"connected": False, "status": "Offline", "reason": f"MT5 Bridge unreachable: {exc}"}

    def account_info(self):
        try:
            return self._request("GET", "/account")
        except Exception:
            return None

    def positions_get(self):
        try:
            return self._request("GET", "/positions") or []
        except Exception:
            return []

    def history_deals_get(self, start=None, end=None, limit=50):
        try:
            params = {"limit": limit}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            return self._request("GET", "/history", params=params) or []
        except Exception:
            return []

    def orders_get(self):
        try:
            return self._request("GET", "/orders") or []
        except Exception:
            return []

    def symbol_info_tick(self, symbol):
        try:
            return self._request("GET", f"/tick?symbol={symbol}")
        except Exception:
            return None

    def order_send(self, payload):
        try:
            return self._request("POST", "/order", json=payload)
        except Exception:
            return None

    def send_command(self, command, bot_id=None, bot_path=None, wait_for_ack=False, session_id=None):
        try:
            body = {"command": command, "bot_id": bot_id, "bot_path": bot_path, "wait_for_ack": bool(wait_for_ack), "session_id": session_id}
            return self._request("POST", "/command", json=body)
        except Exception as exc:
            logger.exception("Failed to send bridge command: %s", exc)
            return {"ok": False, "message": "Bridge unreachable"}
