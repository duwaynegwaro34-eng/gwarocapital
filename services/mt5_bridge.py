import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import logging

from config import settings as app_settings

# Do not import MetaTrader5 at module import time; import lazily where needed.


class MT5Bridge:
    def __init__(self, base_dir=None, mt5_manager=None):
        self._mt5_manager = mt5_manager
        self.base_dir = Path(self._resolve_bridge_dir(base_dir))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._command_file = self.base_dir / "latest_command.json"
        self._status_file = self.base_dir / "latest_status.json"
        self._mt5_manager = mt5_manager
        self._lock = threading.RLock()
        self._state = {
            "state": "stopped",
            "active_bot_id": None,
            "active_bot_path": None,
            "last_command": None,
            "last_error": None,
            "updated_at": None,
        }
        self._command_dir = self.base_dir / "commands"
        self._status_dir = self.base_dir / "status"
        self._command_dir.mkdir(parents=True, exist_ok=True)
        self._status_dir.mkdir(parents=True, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _resolve_bridge_dir(self, base_dir=None):
        if base_dir:
            return base_dir
        mt5_bridge_env = os.getenv("MT5_BRIDGE_DIR")
        if mt5_bridge_env:
            return mt5_bridge_env
        if self._mt5_manager is not None:
            try:
                import MetaTrader5 as _mt5
                if not _mt5.initialize():
                    raise RuntimeError("MT5 initialize failed")
                terminal_info = _mt5.terminal_info()
                if terminal_info is not None and terminal_info.data_path:
                    return os.path.join(terminal_info.data_path, "MQL5", "Files", "gwaro_mt5_bridge")
            except Exception:
                # If MetaTrader5 isn't available in this environment, fall back
                pass
        return getattr(app_settings, "mt5_bridge_dir", None) or os.path.join(os.getcwd(), "instance", "mt5_bridge")

    def _write_json(self, path, payload):
        try:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            logger = logging.getLogger("gwaro.mt5_bridge")
            logger.info("Wrote bridge file: %s", str(path))
            logger.debug("Contents: %s", json.dumps(payload, sort_keys=True))
            return True
        except Exception:
            logger = logging.getLogger("gwaro.mt5_bridge")
            logger.exception("Failed to write bridge file: %s", str(path))
            return False

    def _read_json(self, path, default=None):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def connection_status(self):
        if self._mt5_manager is None:
            # Allow write-only bridge mode when no MT5 manager is present so the
            # GWARO DOLLAR PRINTER EA can still read commands from the shared folder.
            return {"connected": True, "status": "BridgeOnly", "reason": "No MT5 manager configured (bridge-only)"}
        status = self._mt5_manager.connection_status()
        connected = bool(status.get("connected"))
        return {
            "connected": connected,
            "status": status.get("status", "Disconnected"),
            "reason": "MetaTrader 5 is connected" if connected else (status.get("last_error") or "MetaTrader 5 is disconnected"),
        }

    def wait_for_state(self, target_state, timeout=5.0, poll_interval=0.2):
        deadline = time.time() + timeout
        last_error = None
        target_norm = str(target_state).lower()
        if (self._state.get("state") or "").lower() == target_norm:
            return True, dict(self._state)

        while time.time() < deadline:
            status = self.get_status()
            state = (status.get("state") or "").lower()
            if state == target_norm:
                return True, status
            last_error = status.get("last_error")
            if state in {"stopped", "running"} and state != target_norm:
                return False, status
            time.sleep(poll_interval)
        return False, {**self.get_status(), "last_error": last_error or "Timed out waiting for MT5 controller acknowledgement"}

    def send_command(self, command, bot_id, bot_path=None, wait_for_ack=False, timeout=5.0, poll_interval=0.2):
        with self._lock:
            cmd_norm = (str(command) or "").strip()
            cmd_up = cmd_norm.upper()
            cmd_low = cmd_up.lower()
            logger = logging.getLogger("gwaro.mt5_bridge")
            logger.info("send_command called: command=%s bot_id=%s bot_path=%s", cmd_up, bot_id, bot_path)
            payload = {
                "command": cmd_up,
                "bot_id": bot_id,
                "bot_path": bot_path,
                "timestamp": self._now(),
            }
            target_state = "running" if cmd_low == "start" else "stopped" if cmd_low == "stop" else None
            self._state.update({
                "state": "pending",
                "active_bot_id": bot_id if cmd_low == "start" else None,
                "active_bot_path": bot_path if cmd_low == "start" else None,
                "last_command": cmd_up,
                "last_error": None,
                "updated_at": self._now(),
            })
            ts_path = self._command_dir / f"{cmd_low}-{int(time.time()*1000)}.json"
            latest_json = self.base_dir / "latest_command.json"
            latest_txt = self.base_dir / "latest_command.txt"
            self._write_json(ts_path, payload)
            self._write_json(latest_json, payload)
            try:
                latest_txt.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            except Exception:
                logging.getLogger("gwaro.mt5_bridge").exception("Failed to write latest_command.txt")

            self._write_json(self._status_dir / "current_status.json", self._state)
            self._write_json(self._status_file, self._state)
            self._write_json(self._command_file, payload)
            try:
                status_txt = self.base_dir / "latest_status.txt"
                status_txt.write_text(json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8")
            except Exception:
                logging.getLogger("gwaro.mt5_bridge").exception("Failed to write latest_status.txt")

        if self._mt5_manager is None and wait_for_ack and target_state:
            wait_for_ack = False

        if wait_for_ack and target_state:
            ok, state = self.wait_for_state(target_state, timeout=timeout, poll_interval=poll_interval)
            if not ok:
                return False, state.get("last_error") or f"MT5 EA did not acknowledge {cmd_up}"
            with self._lock:
                self._state.update({
                    "state": state.get("state", target_state),
                    "updated_at": self._now(),
                })
                self._write_json(self._status_dir / "current_status.json", self._state)
                self._write_json(self._status_file, self._state)
            return True, f"{cmd_up.title()} acknowledged by the MT5 EA"

        return True, f"{command.title()} command queued for {bot_id}"

    def get_status(self):
        with self._lock:
            current = {}
            current.update(self._read_json(self._status_dir / "current_status.json", {}) or {})
            current.update(self._read_json(self._status_file, {}) or {})
            current.update(self._state)
            current.setdefault("state", "stopped")
            current.setdefault("active_bot_id", None)
            current.setdefault("active_bot_path", None)
            current.setdefault("last_command", None)
            current.setdefault("last_error", None)
            current.setdefault("updated_at", self._now())
            return current

    def sync_from_terminal(self):
        with self._lock:
            file_state = self._read_json(self._status_dir / "current_status.json", {}) or {}
            file_state2 = self._read_json(self._status_file, {}) or {}
            merged = dict(self._state)
            if isinstance(file_state, dict):
                merged.update(file_state)
            if isinstance(file_state2, dict):
                merged.update(file_state2)
            merged.setdefault("state", "stopped")
            merged.setdefault("last_error", None)
            merged.setdefault("updated_at", self._now())
            self._state = merged
            self._write_json(self._status_dir / "current_status.json", self._state)
            self._write_json(self._status_file, self._state)
        return self.get_status()
