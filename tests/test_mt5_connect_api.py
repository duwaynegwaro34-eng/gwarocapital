import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class MT5ConnectApiTests(unittest.TestCase):
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

    def test_mt5_status_endpoint_exists(self):
        response = self.client.get("/api/mt5/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("connected", payload)
        self.assertIn("status", payload)

    def test_mt5_connect_endpoint_validation(self):
        response = self.client.post(
            "/api/mt5/connect",
            json={"login": "", "password": "", "server": ""},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("ok", payload)
        self.assertFalse(payload["ok"])

    def test_mt5_disconnect_endpoint_exists(self):
        response = self.client.post("/api/mt5/disconnect")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("ok", payload)

    def test_mt5_connect_endpoint_uses_manager_initialization(self):
        with patch.object(app_module.mt5_manager, "initialize_client", return_value=True) as init_mock:
            response = self.client.post(
                "/api/mt5/connect",
                json={"login": "12345", "password": "secret", "server": "broker"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        init_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
