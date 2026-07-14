import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class Phase9AnalyticsTests(unittest.TestCase):
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
                username="phase9",
                email="phase9@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()

            now = datetime.now(timezone.utc)
            seeded = [
                ("p9-1", "101", "XAUUSD", 125.0, "Hybrid Bot", now - timedelta(days=2), now - timedelta(days=2, hours=-1)),
                ("p9-2", "102", "EURUSD", -42.0, "Gwaro Dollar Printer", now - timedelta(days=1), now - timedelta(days=1, hours=-1)),
                ("p9-3", "103", "GBPUSD", 67.0, "Scalper Newest", now - timedelta(hours=6), now - timedelta(hours=5)),
                ("p9-4", "104", "XAUUSD", 88.0, "Hybrid Bot", now - timedelta(hours=4), now - timedelta(hours=3)),
            ]

            for journal_event_id, ticket, symbol, profit, bot_name, open_time, close_time in seeded:
                app_module.db.session.add(
                    app_module.TradeJournalEntry(
                        journal_event_id=journal_event_id,
                        ticket=ticket,
                        symbol=symbol,
                        entry_price=2300.0 if symbol == "XAUUSD" else 1.1,
                        exit_price=2301.5 if profit >= 0 else 1.098,
                        profit_loss=profit,
                        open_time=open_time,
                        close_time=close_time,
                        strategy_bot=bot_name,
                        status="CLOSED",
                    )
                )
            app_module.db.session.commit()

        self.client.post(
            "/login",
            data={"email": "phase9@example.com", "password": "secret123"},
            follow_redirects=True,
        )

    def test_dashboard_and_history_pages_render(self):
        dashboard_response = self.client.get("/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn(b"Live Analytics Charts", dashboard_response.data)

        history_response = self.client.get("/history")
        self.assertEqual(history_response.status_code, 200)
        self.assertIn(b"Trade History", history_response.data)

    def test_dashboard_summary_api_contains_widgets(self):
        response = self.client.get("/api/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        required = [
            "best_performing_bot",
            "worst_performing_bot",
            "largest_win_today",
            "largest_loss_today",
            "current_floating_profit",
            "current_drawdown",
            "open_positions",
            "closed_trades_today",
            "active_trading_sessions",
            "mt5_connection_health",
        ]
        for key in required:
            self.assertIn(key, payload)

    def test_performance_and_bot_statistics_apis(self):
        perf_response = self.client.get("/api/dashboard/performance-summary")
        self.assertEqual(perf_response.status_code, 200)
        perf_payload = perf_response.get_json()
        for key in [
            "today_profit_loss",
            "weekly_profit_loss",
            "monthly_profit_loss",
            "average_profit_per_trade",
            "average_loss_per_trade",
            "current_drawdown",
            "floating_profit_loss",
            "roi_percent",
        ]:
            self.assertIn(key, perf_payload)

        bot_response = self.client.get("/api/dashboard/bot-statistics")
        self.assertEqual(bot_response.status_code, 200)
        bot_payload = bot_response.get_json()
        self.assertIn("items", bot_payload)
        self.assertEqual(len(bot_payload["items"]), 3)
        self.assertIsNotNone(bot_payload["best_bot"])
        self.assertIsNotNone(bot_payload["worst_bot"])

    def test_chart_and_trade_history_apis(self):
        chart_response = self.client.get("/api/dashboard/chart-data")
        self.assertEqual(chart_response.status_code, 200)
        chart_payload = chart_response.get_json()
        for key in [
            "equity_curve",
            "balance_history",
            "daily_profit",
            "weekly_profit",
            "monthly_profit",
            "win_rate_history",
            "drawdown_history",
        ]:
            self.assertIn(key, chart_payload)
            self.assertIsInstance(chart_payload[key], list)

        trade_response = self.client.get("/api/dashboard/trade-history?bot=Hybrid%20Bot")
        self.assertEqual(trade_response.status_code, 200)
        trade_payload = trade_response.get_json()
        self.assertIn("items", trade_payload)
        self.assertTrue(all(item["bot_used"] == "Hybrid Bot" for item in trade_payload["items"]))

    def test_trade_history_exports(self):
        csv_response = self.client.get("/api/dashboard/trade-history/export?format=csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(b"Ticket,Symbol,Buy/Sell", csv_response.data)

        xlsx_response = self.client.get("/api/dashboard/trade-history/export?format=excel")
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertTrue(xlsx_response.data.startswith(b"PK"))

    def test_notifications_api_available(self):
        response = self.client.get("/api/dashboard/notifications")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("items", payload)


if __name__ == "__main__":
    unittest.main()
