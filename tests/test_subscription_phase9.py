import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class SubscriptionPhase9Tests(unittest.TestCase):
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

            self.user1 = app_module.User(
                username="user1",
                email="user1@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
                mt5_account="999999",
            )
            self.user2 = app_module.User(
                username="user2",
                email="user2@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
                mt5_account="999999",
            )
            app_module.db.session.add(self.user1)
            app_module.db.session.add(self.user2)
            app_module.db.session.commit()

    def login_user(self, email):
        return self.client.post(
            "/login",
            data={"email": email, "password": "secret123"},
            follow_redirects=True,
        )

    def test_renew_subscription_flow(self):
        # user1 upgrades, cancels, then renews
        self.login_user("user1@example.com")
        r = self.client.post("/api/subscription/upgrade", json={"plan": "MONTHLY", "provider": "mpesa"}, headers={"X-CSRF-Token": "ignored-in-testing"})
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertTrue(payload["ok"])

        # cancel
        r2 = self.client.post("/api/subscription/cancel", headers={"X-CSRF-Token": "ignored-in-testing"})
        self.assertEqual(r2.status_code, 200)
        p2 = r2.get_json()
        self.assertEqual(p2["subscription"]["status"], "EXPIRED")

        # renew
        r3 = self.client.post("/api/subscription/renew", headers={"X-CSRF-Token": "ignored-in-testing"})
        self.assertEqual(r3.status_code, 200)
        p3 = r3.get_json()
        self.assertTrue(p3["ok"])
        self.assertEqual(p3["subscription"]["status"], "ACTIVE")

    def test_prevent_duplicate_mt5_license(self):
        # user1 creates license
        self.login_user("user1@example.com")
        r = self.client.post("/api/subscription/upgrade", json={"plan": "LIFETIME", "provider": "card"}, headers={"X-CSRF-Token": "ignored-in-testing"})
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["license"]["status"], "ACTIVE")

        # user2 attempts to create license for same MT5 account
        self.client.get("/logout", follow_redirects=True)
        self.login_user("user2@example.com")
        r2 = self.client.post("/api/subscription/upgrade", json={"plan": "MONTHLY", "provider": "mpesa"}, headers={"X-CSRF-Token": "ignored-in-testing"})
        # Expect conflict due to MT5 already licensed
        self.assertEqual(r2.status_code, 409)
        p2 = r2.get_json()
        self.assertFalse(p2["ok"]) if "ok" in p2 else None
        self.assertIn("MT5 account already licensed", p2.get("message", ""))


if __name__ == "__main__":
    unittest.main()
