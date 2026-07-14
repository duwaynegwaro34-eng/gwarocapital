import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.bot_manager import BotManager


class FakeBotModule:
    def stop(self):
        return None


class DynamicBotDiscoveryTests(unittest.TestCase):
    def test_discovery_uses_experts_directory_and_selected_bot_controls_start_stop(self):
        with tempfile.TemporaryDirectory() as tempdir:
            nested_dir = Path(tempdir) / "Strategy" / "Live"
            nested_dir.mkdir(parents=True)
            (nested_dir / "MyEA.ex5").touch()
            (nested_dir / "SecondEA.ex4").touch()
            (Path(tempdir) / "StandaloneEA.mq5").touch()

            manager = BotManager(FakeBotModule())
            with patch("services.bot_manager.mt5_manager.connection_status", return_value={"connected": True, "status": "Connected"}):
                discovered = manager.discover_available_bots(experts_dir=tempdir)

            self.assertEqual([bot["id"] for bot in discovered], ["standaloneea", "myea", "secondea"])
            self.assertEqual([bot["name"] for bot in discovered], ["StandaloneEA", "MyEA", "SecondEA"])

            manager._engine.start = Mock(return_value=(True, "Bot started"))
            manager._engine.stop = Mock(return_value=(True, "Bot stopped"))
            manager._engine.status = Mock(return_value={"running": False, "error": "", "start_time": None, "last_execution": None, "uptime": "00:00:00"})

            ok, message = manager.start(bot_id="myea")
            self.assertTrue(ok)
            self.assertEqual(manager.status()["current_bot_id"], "myea")

            stop_ok, stop_message = manager.stop(bot_id="myea")
            self.assertTrue(stop_ok)
            self.assertIn("stopped", stop_message.lower())


if __name__ == "__main__":
    unittest.main()
