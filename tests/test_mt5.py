import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class MT5EndpointTests(unittest.TestCase):
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

    def test_mt5_account_status_endpoint_returns_disconnected_payload(self):
        response = self.client.get("/api/mt5/account")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertIn("connected", payload)
        self.assertIn("status", payload)

    def test_mt5_status_endpoint_is_available(self):
        response = self.client.get("/api/mt5/status")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertIn("connected", payload)
        self.assertIn("status", payload)


if __name__ == "__main__":
    unittest.main()
