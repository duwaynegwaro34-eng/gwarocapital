import json
import os
import sys
import time
from pathlib import Path


class MT5BridgeController:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or os.path.join(os.getcwd(), "instance", "mt5_bridge"))
        self.command_dir = self.base_dir / "commands"
        self.status_dir = self.base_dir / "status"
        self.command_dir.mkdir(parents=True, exist_ok=True)
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self._processed = set()

    def _write_status(self, payload):
        self.status_dir.mkdir(parents=True, exist_ok=True)
        (self.status_dir / "current_status.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def run(self, interval=1.0):
        while True:
            for path in sorted(self.command_dir.glob("*.json")):
                if path.name in self._processed:
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    command = (payload.get("command") or "").lower()
                    bot_id = payload.get("bot_id") or ""
                    bot_path = payload.get("bot_path")
                    supported_bot_ids = {"gwarodollarprinter", "gwaro dollar printer"}
                    if bot_id and str(bot_id).lower() not in supported_bot_ids:
                        self._write_status({
                            "state": "stopped",
                            "active_bot_id": None,
                            "active_bot_path": None,
                            "last_command": command,
                            "last_error": "Unsupported bot for single-bot controller",
                            "updated_at": payload.get("timestamp"),
                        })
                        continue
                    if command == "start":
                        self._write_status({
                            "state": "running",
                            "active_bot_id": bot_id,
                            "active_bot_path": bot_path,
                            "last_command": "start",
                            "last_error": None,
                            "updated_at": payload.get("timestamp"),
                        })
                    elif command == "stop":
                        self._write_status({
                            "state": "stopped",
                            "active_bot_id": None,
                            "active_bot_path": None,
                            "last_command": "stop",
                            "last_error": None,
                            "updated_at": payload.get("timestamp"),
                        })
                    elif command in {"close_all", "close_all_trades", "closeall"}:
                        self._write_status({
                            "state": "stopped",
                            "active_bot_id": None,
                            "active_bot_path": None,
                            "last_command": "close_all",
                            "last_error": None,
                            "updated_at": payload.get("timestamp"),
                        })
                    elif command == "break_even":
                        self._write_status({
                            "state": "running",
                            "active_bot_id": bot_id,
                            "active_bot_path": bot_path,
                            "last_command": "break_even",
                            "last_error": None,
                            "updated_at": payload.get("timestamp"),
                        })
                    else:
                        self._write_status({
                            "state": "stopped",
                            "active_bot_id": None,
                            "active_bot_path": None,
                            "last_command": command,
                            "last_error": "Unsupported command",
                            "updated_at": payload.get("timestamp"),
                        })
                except Exception as exc:
                    self._write_status({
                        "state": "stopped",
                        "last_command": "error",
                        "last_error": str(exc),
                        "updated_at": None,
                    })
                finally:
                    self._processed.add(path.name)
            time.sleep(interval)


if __name__ == "__main__":
    controller = MT5BridgeController()
    print("MT5 bridge controller started")
    controller.run()
