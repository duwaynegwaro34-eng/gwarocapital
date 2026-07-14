import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class Phase8SubscriptionAdminTests(unittest.TestCase):
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

            self.user = app_module.User(
                username="phase8-user",
                email="phase8@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
                mt5_account="12345678",
            )
            self.admin = app_module.User(
                username="phase8-admin",
                email="admin@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
                mt5_account="87654321",
            )
            app_module.db.session.add(self.user)
            app_module.db.session.add(self.admin)
            app_module.db.session.commit()
            self.user_id = self.user.id
            self.admin_id = self.admin.id
            app_module.db.session.add(app_module.AdminRole(user_id=self.admin_id, is_active=True))
            app_module.db.session.commit()

    def login_user(self, email="phase8@example.com"):
        return self.client.post(
            "/login",
            data={"email": email, "password": "secret123"},
            follow_redirects=True,
        )

    def test_subscription_upgrade_and_cancel_flow(self):
        self.login_user()

        upgrade_response = self.client.post(
            "/api/subscription/upgrade",
            json={"plan": "MONTHLY", "provider": "mpesa"},
            headers={"X-CSRF-Token": "ignored-in-testing"},
        )
        self.assertEqual(upgrade_response.status_code, 200)
        upgrade_payload = upgrade_response.get_json()
        self.assertTrue(upgrade_payload["ok"])
        self.assertEqual(upgrade_payload["subscription"]["plan"], "MONTHLY")
        self.assertEqual(upgrade_payload["license"]["status"], "ACTIVE")

        status_response = self.client.get("/api/subscription/status")
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.get_json()
        self.assertEqual(status_payload["plan"], "MONTHLY")
        self.assertTrue(status_payload["is_active"])

        cancel_response = self.client.post(
            "/api/subscription/cancel",
            headers={"X-CSRF-Token": "ignored-in-testing"},
        )
        self.assertEqual(cancel_response.status_code, 200)
        cancel_payload = cancel_response.get_json()
        self.assertTrue(cancel_payload["ok"])
        self.assertEqual(cancel_payload["subscription"]["status"], "EXPIRED")

    def test_payment_history_endpoint(self):
        self.login_user()
        self.client.post(
            "/api/subscription/upgrade",
            json={"plan": "LIFETIME", "provider": "paypal"},
            headers={"X-CSRF-Token": "ignored-in-testing"},
        )

        history_response = self.client.get("/api/payments/history")
        self.assertEqual(history_response.status_code, 200)
        history_payload = history_response.get_json()
        self.assertIn("items", history_payload)
        self.assertGreaterEqual(len(history_payload["items"]), 1)

    def test_license_validation_endpoint(self):
        self.login_user()
        self.client.post(
            "/api/subscription/upgrade",
            json={"plan": "MONTHLY", "provider": "card"},
            headers={"X-CSRF-Token": "ignored-in-testing"},
        )

        response = self.client.get("/api/licenses/validate?mt5_account=12345678")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("ok", payload)
        self.assertIn("license", payload)
        self.assertEqual(payload["license"]["mt5_account"], "12345678")

    def test_developer_license_bypass_allows_missing_license(self):
        app_module.app_settings.developer_mt5_accounts = {"12345678"}
        self.login_user()

        with app_module.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            ok, message = app_module.validate_license_for_bot_start(user)

        self.assertTrue(ok)
        self.assertEqual(message, "Developer Mode: License check bypassed.")

    def test_admin_dashboard_and_metrics(self):
        self.login_user(email="admin@example.com")

        dashboard_response = self.client.get("/admin")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn(b"Admin", dashboard_response.data)

        metrics_response = self.client.get("/api/admin/metrics")
        self.assertEqual(metrics_response.status_code, 200)
        metrics_payload = metrics_response.get_json()
        self.assertIn("total_users", metrics_payload)
        self.assertIn("active_subscriptions", metrics_payload)
        self.assertIn("revenue_summary", metrics_payload)

    def test_admin_license_management_endpoints(self):
        self.login_user()
        self.client.post(
            "/api/subscription/upgrade",
            json={"plan": "MONTHLY", "provider": "mpesa"},
            headers={"X-CSRF-Token": "ignored-in-testing"},
        )

        self.client.get("/logout", follow_redirects=True)
        self.login_user(email="admin@example.com")
        list_response = self.client.get("/api/admin/licenses")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.get_json()
        self.assertIn("items", payload)
        self.assertGreaterEqual(len(payload["items"]), 1)
        license_id = payload["items"][0]["id"]

        update_response = self.client.post(
            f"/api/admin/licenses/{license_id}/status",
            json={"status": "INACTIVE"},
            headers={"X-CSRF-Token": "ignored-in-testing"},
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.get_json()
        self.assertTrue(update_payload["ok"])

    def test_health_endpoint_available(self):
        response = self.client.get("/health")
        self.assertIn(response.status_code, [200, 503])
        payload = response.get_json()
        self.assertIn("status", payload)
        self.assertIn("database", payload)


if __name__ == "__main__":
    unittest.main()
