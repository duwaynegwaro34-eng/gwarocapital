import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class NavigationTests(unittest.TestCase):
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
                username="navtester",
                email="navtester@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()

    def _login(self):
        return self.client.post(
            "/login",
            data={"email": "navtester@example.com", "password": "secret123"},
            follow_redirects=True,
        )

    def test_sidebar_routes_render_for_authenticated_users(self):
        self._login()

        routes = [
            ("/dashboard", "Dashboard"),
            ("/bot-control", "Bot Control"),
            ("/markets", "Markets"),
            ("/ai-signals", "AI Signals"),
            ("/mt5", "MT5"),
            ("/history", "Trade History"),
            ("/settings", "Settings"),
        ]

        for path, expected in routes:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected.encode("utf-8"), response.data)

    def test_logout_redirects_to_login(self):
        self._login()
        response = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"login", response.data.lower())


if __name__ == "__main__":
    unittest.main()
