import unittest
from unittest.mock import patch

from services.bot_manager import BotManager


class BotManagerControlActionsTest(unittest.TestCase):
    def setUp(self):
        self.manager = BotManager(bot_module=object())

    def test_close_all_trades_dispatches_a_bridge_command(self):
        with patch.object(self.manager._bridge, "send_command", return_value=(True, "acked")) as mocked_send:
            ok, message = self.manager.close_all_trades()

        self.assertTrue(ok)
        self.assertIn("close", message.lower())
        mocked_send.assert_called_once()

    def test_break_even_dispatches_a_bridge_command(self):
        with patch.object(self.manager._bridge, "send_command", return_value=(True, "acked")) as mocked_send:
            ok, message = self.manager.break_even()

        self.assertTrue(ok)
        self.assertIn("break", message.lower())
        mocked_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
