import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.mt5_bridge import MT5Bridge


class FakeMT5Manager:
    def __init__(self, connected=True):
        self.connected = connected

    def connection_status(self):
        return {"connected": self.connected, "status": "Connected" if self.connected else "Disconnected"}


class MT5BridgeTests(unittest.TestCase):
    def test_bridge_writes_commands_and_reports_status(self):
        with tempfile.TemporaryDirectory() as tempdir:
            bridge = MT5Bridge(base_dir=tempdir, mt5_manager=FakeMT5Manager(True))

            ok, message = bridge.send_command("start", "myea", bot_path=r"C:\Experts\MyEA.ex5")
            self.assertTrue(ok)
            self.assertIn("start", message.lower())

            state = bridge.get_status()
            self.assertEqual(state["state"], "pending")
            self.assertEqual(state["active_bot_id"], "myea")
            self.assertEqual(state["active_bot_path"], r"C:\Experts\MyEA.ex5")
            self.assertTrue((bridge.base_dir / "latest_command.json").exists())
            self.assertTrue((bridge.base_dir / "latest_status.json").exists())

            stop_ok, stop_message = bridge.send_command("stop", "myea")
            self.assertTrue(stop_ok)
            self.assertIn("stop", stop_message.lower())


if __name__ == "__main__":
    unittest.main()
