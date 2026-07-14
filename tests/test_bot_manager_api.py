import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class BotManagerApiTests(unittest.TestCase):
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
                username="botuser",
                email="botuser@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()

        self.client.post(
            "/login",
            data={"email": "botuser@example.com", "password": "secret123"},
            follow_redirects=True,
        )

    def test_bot_status_endpoint(self):
        response = self.client.get("/api/bot/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("current_bot", payload)
        self.assertIn("running", payload)
        self.assertIn("bots", payload)
        self.assertIn("activity_log", payload)
        self.assertTrue(payload["bots"])
        self.assertTrue(all("id" in bot and "name" in bot for bot in payload["bots"]))

    def test_bot_select_and_start_stop(self):
        status_response = self.client.get("/api/bot/status")
        payload = status_response.get_json()
        first_bot = payload["bots"][0]
        bot_id = first_bot["id"]

        select_response = self.client.post("/api/bot/select", json={"bot_id": bot_id})
        self.assertEqual(select_response.status_code, 200)
        select_payload = select_response.get_json()
        self.assertTrue(select_payload["ok"])
        self.assertEqual(select_payload["current_bot_id"], bot_id)

        start_response = self.client.post("/api/bot/start", json={"bot_id": bot_id})
        self.assertEqual(start_response.status_code, 200)
        start_payload = start_response.get_json()
        self.assertIn("ok", start_payload)
        self.assertIn("status", start_payload)
        self.assertIn(start_payload["status"], ["Running", "Stopped", "Error"])

        stop_response = self.client.post("/api/bot/stop", json={"bot_id": bot_id})
        self.assertEqual(stop_response.status_code, 200)
        stop_payload = stop_response.get_json()
        self.assertIn("ok", stop_payload)
        self.assertIn("status", stop_payload)

    def test_stop_only_selected_bot_guard(self):
        manager = app_module.bot_manager

        original_running = manager._engine._running
        original_active_bot = manager._active_bot

        try:
            manager._active_bot = "hybrid_bot"
            manager._engine._running = True

            response = self.client.post("/api/bot/stop", json={"bot_id": "scalper_newest"})
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertIn("ok", payload)
            self.assertFalse(payload["ok"])
            self.assertIn("selected bot does not match", payload["message"].lower())
        finally:
            manager._engine._running = original_running
            manager._active_bot = original_active_bot

    def test_activity_log_and_legacy_bot_status_route(self):
        status_response = self.client.get("/api/bot/status")
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.get_json()
        self.assertIn("activity_log", status_payload)
        self.assertIsInstance(status_payload["activity_log"], list)

        legacy_response = self.client.get("/bot_status")
        self.assertEqual(legacy_response.status_code, 200)
        legacy_payload = legacy_response.get_json()
        self.assertIn("logs", legacy_payload)
        self.assertIsInstance(legacy_payload["logs"], list)

    def test_control_routes_return_shared_payload_fields(self):
        response = self.client.post("/api/bot/start", json={"bot_id": "gwarodollarprinter"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("success", payload)
        self.assertIn("message", payload)
        self.assertIn("status", payload)
        self.assertIn("uptime", payload)
        self.assertIn("last_signal", payload)
        self.assertIn("mt5_connected", payload)
        self.assertIsInstance(payload["mt5_connected"], bool)

    def test_restart_route_returns_shared_payload_fields(self):
        with patch.object(app_module.bot_manager, "restart", return_value=(True, "restarted")) as restart_mock:
            response = self.client.post("/api/bot/restart", json={"bot_id": "gwarodollarprinter"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["message"], "restarted")
            self.assertIn("success", payload)
            self.assertIn("status", payload)
            self.assertIn("uptime", payload)
            self.assertIn("last_signal", payload)
            self.assertIn("mt5_connected", payload)
            restart_mock.assert_called_once()

    def test_close_all_and_break_even_alias_routes(self):
        with patch.object(app_module.bot_manager, "close_all_trades", return_value=(True, "closed")) as close_mock:
            response = self.client.post("/api/bot/close-all", json={"bot_id": "gwarodollarprinter"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["message"], "closed")
            close_mock.assert_called_once_with(bot_id="gwarodollarprinter")

        with patch.object(app_module.bot_manager, "break_even", return_value=(True, "break-even")) as break_mock:
            response = self.client.post("/api/bot/breakeven", json={"bot_id": "gwarodollarprinter"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["message"], "break-even")
            break_mock.assert_called_once_with(bot_id="gwarodollarprinter")

    def test_bridge_wait_for_state_confirms_controller_acknowledgement(self):
        self.client.post("/api/bot/stop", json={"bot_id": "gwarodollarprinter"})

        ok, status = app_module.bot_manager._bridge.wait_for_state("stopped", timeout=0.2)
        self.assertTrue(ok)
        self.assertEqual(status.get("state"), "stopped")


if __name__ == "__main__":
    unittest.main()
