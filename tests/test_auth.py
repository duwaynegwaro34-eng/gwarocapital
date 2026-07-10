import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class AuthFlowTests(unittest.TestCase):
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

    def test_register_login_and_logout(self):
        register_response = self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
            },
            follow_redirects=True,
        )
        self.assertEqual(register_response.status_code, 200)

        login_response = self.client.post(
            "/login",
            data={
                "email": "alice@example.com",
                "password": "secret123",
            },
            follow_redirects=True,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn(b"dashboard", login_response.data.lower())

        with self.client.session_transaction() as session:
            self.assertIn("user_id", session)

        logout_response = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_duplicate_registration_shows_friendly_message(self):
        self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
            },
        )

        duplicate_response = self.client.post(
            "/register",
            data={
                "username": "alice2",
                "email": "alice@example.com",
                "password": "secret123",
            },
            follow_redirects=True,
        )

        self.assertEqual(duplicate_response.status_code, 200)
        self.assertIn(b"email already exists", duplicate_response.data.lower())

    def test_dashboard_requires_authentication(self):
        response = self.client.get("/dashboard", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"login", response.data.lower())


if __name__ == "__main__":
    unittest.main()
