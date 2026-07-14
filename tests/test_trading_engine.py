import os
import sys
import time
import types
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.trading_engine as trading_engine_module
from services.trading_engine import TradingEngine


class FakePosition:
    def __init__(self, ticket, symbol, position_type, volume, profit):
        self.ticket = ticket
        self.symbol = symbol
        self.type = position_type
        self.volume = volume
        self.profit = profit


class FakeMT5:
    def __init__(self):
        self._position_calls = 0

    def account_info(self):
        return object()

    def positions_get(self):
        self._position_calls += 1
        if self._position_calls == 1:
            return []
        if self._position_calls == 2:
            return [FakePosition(1001, "XAUUSD", 0, 0.01, 12.3)]
        return []


class FakeMT5Manager:
    def __init__(self):
        self.connected = True

    def initialize_client(self):
        return self.connected

    def shutdown_client(self):
        return None


class FakeBotModule:
    def __init__(self):
        self.cycles = 0
        self.stopped = False
        self.last_configuration = None

    def reset_trading_day(self):
        self.cycles += 1

    def capture_session(self):
        self.cycles += 1

    def check_strategy(self):
        self.cycles += 1

    def manage_trade(self):
        self.cycles += 1

    def trailing_stop(self):
        self.cycles += 1

    def configure_execution(self, bot_id, bot_path, chart_symbol=None):
        self.last_configuration = {
            "bot_id": bot_id,
            "bot_path": bot_path,
            "chart_symbol": chart_symbol,
        }

    def stop(self):
        self.stopped = True


class TradingEngineTests(unittest.TestCase):
    def test_trading_engine_emits_trade_open_and_close_events(self):
        events = []
        fake_bot = FakeBotModule()
        fake_mt5_manager = FakeMT5Manager()

        original_mt5 = trading_engine_module.mt5
        trading_engine_module.mt5 = FakeMT5()

        try:
            engine = TradingEngine(
                fake_bot,
                fake_mt5_manager,
                event_callback=lambda event: events.append(event),
                poll_interval=0.05,
            )

            ok, _ = engine.start("hybrid_bot")
            self.assertTrue(ok)

            # Sleep long enough to guarantee multiple poll cycles:
            # With poll_interval=0.05, we need at least 3 iterations:
            # Iteration 1: positions=[] → no events
            # Iteration 2: positions=[1001] → Trade Opened
            # Iteration 3: positions=[] → Trade Closed
            time.sleep(0.5)

            ok, _ = engine.stop()
            self.assertTrue(ok)

            event_types = [event["type"] for event in events]
            self.assertIn("Trade Opened", event_types)
            self.assertIn("Trade Closed", event_types)
            self.assertGreater(fake_bot.cycles, 0)
            self.assertTrue(fake_bot.stopped)
        finally:
            trading_engine_module.mt5 = original_mt5

    def test_trading_engine_accepts_any_discovered_bot_and_tracks_activation(self):
        events = []
        fake_bot = FakeBotModule()
        fake_mt5_manager = FakeMT5Manager()

        engine = TradingEngine(
            fake_bot,
            fake_mt5_manager,
            event_callback=lambda event: events.append(event),
            poll_interval=0.05,
        )
        engine.set_bot_registry({
            "myea": {
                "id": "myea",
                "name": "MyEA",
                "path": r"C:\\Experts\\MyEA.ex5",
            }
        })

        ok, _ = engine.start("myea")
        self.assertTrue(ok)
        self.assertEqual(engine._active_bot_id, "myea")
        self.assertEqual(fake_bot.last_configuration["bot_id"], "myea")
        self.assertTrue(any(event["type"] == "Bot Activated" for event in events))

        ok, _ = engine.stop()
        self.assertTrue(ok)
        self.assertIsNone(engine._active_bot_id)
        self.assertTrue(any(event["type"] == "Bot Deactivated" for event in events))

    def test_trading_engine_sets_error_when_mt5_unavailable(self):
        events = []
        fake_bot = FakeBotModule()
        fake_mt5_manager = FakeMT5Manager()
        fake_mt5_manager.connected = False

        engine = TradingEngine(
            fake_bot,
            fake_mt5_manager,
            event_callback=lambda event: events.append(event),
            poll_interval=0.05,
        )

        ok, _ = engine.start("hybrid_bot")
        self.assertTrue(ok)

        time.sleep(0.1)
        status = engine.status()

        self.assertFalse(status["running"])
        self.assertTrue(status["error"])
        self.assertTrue(any(event["type"] == "Errors" for event in events))


if __name__ == "__main__":
    unittest.main()
