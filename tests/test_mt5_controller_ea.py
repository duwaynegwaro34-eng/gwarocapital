import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.mt5_bridge import MT5Bridge


class MT5ControllerEATests(unittest.TestCase):
    def test_bridge_writes_command_and_ack_files(self):
        bridge = MT5Bridge(base_dir=os.path.join(os.getcwd(), "instance", "mt5_bridge_test"), mt5_manager=None)
        ok, message = bridge.send_command("START", "myea", bot_path=r"C:\Experts\MyEA.ex5")
        self.assertTrue(ok)
        self.assertIn("queued", message.lower())
        self.assertTrue((bridge.base_dir / "latest_command.json").exists())
        self.assertTrue((bridge.base_dir / "latest_status.json").exists())


if __name__ == "__main__":
    unittest.main()
