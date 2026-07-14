import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class Phase7AnalyticsTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SECRET_KEY="test-secret",
        )
        self.client = app_module.app.test_client()

        with app_module.app.app_context():
            app_module.db.drop_all()
            app_module.db.create_all()
            user = app_module.User(
                username="phase7",
                email="phase7@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()

            now = datetime.now(timezone.utc)
            e1 = app_module.TradeJournalEntry(
                journal_event_id="seed-1",
                ticket="101",
                symbol="XAUUSD",
                entry_price=2300.0,
                exit_price=2304.2,
                profit_loss=84.0,
                open_time=now - timedelta(hours=3),
                close_time=now - timedelta(hours=2),
                strategy_bot="Hybrid Bot",
                status="CLOSED",
            )
            e2 = app_module.TradeJournalEntry(
                journal_event_id="seed-2",
                ticket="102",
                symbol="EURUSD",
                entry_price=1.1,
                exit_price=1.098,
                profit_loss=-32.0,
                open_time=now - timedelta(hours=2),
                close_time=now - timedelta(hours=1),
                strategy_bot="Scalper Newest",
                status="CLOSED",
            )
            app_module.db.session.add(e1)
            app_module.db.session.add(e2)
            app_module.db.session.commit()

        self.client.post(
            "/login",
            data={"email": "phase7@example.com", "password": "secret123"},
            follow_redirects=True,
        )

    def test_ai_analysis_endpoint_shape(self):
        response = self.client.get("/api/ai/analysis")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("analysis", payload)
        self.assertIsInstance(payload["analysis"], list)

    def test_risk_summary_endpoint_shape(self):
        response = self.client.get("/api/risk/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("recommended_lot_size", payload)
        self.assertIn("current_risk_percent", payload)
        self.assertIn("risk_limit_percent", payload)
        self.assertIn("risk_exceeded", payload)

    def test_performance_summary_endpoint_contains_metrics(self):
        response = self.client.get("/api/performance/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        required = [
            "win_rate",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "net_profit",
            "profit_factor",
            "maximum_drawdown",
        ]
        for key in required:
            self.assertIn(key, payload)

    def test_trading_journal_filter_by_bot(self):
        response = self.client.get("/api/journal?bot=Hybrid%20Bot")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("items", payload)
        self.assertTrue(any(item["bot"] == "Hybrid Bot" for item in payload["items"]))
        self.assertFalse(any(item["bot"] == "Scalper Newest" for item in payload["items"]))

    def test_assistant_summary_contains_required_sections(self):
        response = self.client.get("/api/assistant/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("ai_summary", payload)
        self.assertIn("today_performance", payload)
        self.assertIn("active_bot_summary", payload)
        self.assertIn("risk_manager", payload)
        self.assertIn("performance", payload)
        self.assertIn("notifications", payload)


if __name__ == "__main__":
    unittest.main()
