import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


class FakeSMTP:
    sent_messages = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in_as = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in_as = (username, password)

    def send_message(self, message):
        FakeSMTP.sent_messages.append(message)


class ForgotPasswordTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SECRET_KEY="test-secret",
        )
        self.client = app_module.app.test_client()
        self.original_smtp_host = app_module.app_settings.smtp_host
        self.original_smtp_port = app_module.app_settings.smtp_port
        self.original_smtp_username = app_module.app_settings.smtp_username
        self.original_smtp_password = app_module.app_settings.smtp_password
        self.original_smtp_use_tls = app_module.app_settings.smtp_use_tls
        self.original_smtp_use_ssl = app_module.app_settings.smtp_use_ssl
        self.original_smtp_timeout_seconds = app_module.app_settings.smtp_timeout_seconds
        self.original_smtp_from_email = app_module.app_settings.smtp_from_email
        self.original_smtp_from_name = app_module.app_settings.smtp_from_name
        self.original_password_reset_expiry_minutes = app_module.app_settings.password_reset_expiry_minutes

        app_module.app_settings.smtp_host = "smtp.example.com"
        app_module.app_settings.smtp_port = 587
        app_module.app_settings.smtp_username = "smtp-user"
        app_module.app_settings.smtp_password = "smtp-pass"
        app_module.app_settings.smtp_use_tls = True
        app_module.app_settings.smtp_use_ssl = False
        app_module.app_settings.smtp_timeout_seconds = 10
        app_module.app_settings.smtp_from_email = "noreply@example.com"
        app_module.app_settings.smtp_from_name = "GWARO Capital"
        app_module.app_settings.password_reset_expiry_minutes = 30
        FakeSMTP.sent_messages = []

        with app_module.app.app_context():
            app_module.db.drop_all()
            app_module.db.create_all()
            user = app_module.User(
                username="resetter",
                email="resetter@example.com",
                password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()

    def tearDown(self):
        app_module.app_settings.smtp_host = self.original_smtp_host
        app_module.app_settings.smtp_port = self.original_smtp_port
        app_module.app_settings.smtp_username = self.original_smtp_username
        app_module.app_settings.smtp_password = self.original_smtp_password
        app_module.app_settings.smtp_use_tls = self.original_smtp_use_tls
        app_module.app_settings.smtp_use_ssl = self.original_smtp_use_ssl
        app_module.app_settings.smtp_timeout_seconds = self.original_smtp_timeout_seconds
        app_module.app_settings.smtp_from_email = self.original_smtp_from_email
        app_module.app_settings.smtp_from_name = self.original_smtp_from_name
        app_module.app_settings.password_reset_expiry_minutes = self.original_password_reset_expiry_minutes

    @patch("app.smtplib.SMTP", FakeSMTP)
    def test_forgot_password_request_creates_token_and_sends_email(self):
        response = self.client.post("/forgot-password", data={"email": "resetter@example.com"}, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"check your email", response.data.lower())
        self.assertIn(b"verify reset code", response.data.lower())
        self.assertEqual(len(FakeSMTP.sent_messages), 1)

        with app_module.app.app_context():
            user = app_module.User.query.filter_by(email="resetter@example.com").first()
            record = app_module.PasswordResetToken.query.filter_by(user_id=user.id).first()

        self.assertIsNotNone(record)
        self.assertEqual(record.code.isdigit(), True)
        self.assertEqual(len(record.code), 6)
        self.assertAlmostEqual(
            (record.expires_at - record.created_at).total_seconds(),
            30 * 60,
            delta=5,
        )

        email_message = FakeSMTP.sent_messages[0]
        self.assertEqual(email_message["To"], "resetter@example.com")
        self.assertIn(record.code, email_message.as_string())
        # Token may be split across lines due to MIME quoted-printable encoding,
        # so check for code and that token is present (even if soft-broken with =\n)
        email_str = email_message.as_string()
        # Remove soft line breaks (=\n) to normalize for comparison
        normalized_email = email_str.replace('=\n', '').replace('= \n', '')
        self.assertIn(record.token, normalized_email)

    @patch("app.smtplib.SMTP", FakeSMTP)
    def test_forgot_password_unknown_email_keeps_generic_response(self):
        response = self.client.post("/forgot-password", data={"email": "missing@example.com"}, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"check your email", response.data.lower())
        self.assertIn(b"verify reset code", response.data.lower())
        self.assertEqual(len(FakeSMTP.sent_messages), 0)

    @patch("app.smtplib.SMTP", FakeSMTP)
    def test_verify_code_then_reset_password_updates_password_and_invalidates_token(self):
        with app_module.app.app_context():
            user = app_module.User.query.filter_by(email="resetter@example.com").first()
            token = app_module.create_password_reset_token(user)
            record = app_module.PasswordResetToken.query.filter_by(user_id=user.id).first()

        with self.client.session_transaction() as test_session:
            test_session["password_reset_user_id"] = user.id

        verify_response = self.client.post(
            "/verify-reset-code",
            data={"code": record.code},
            follow_redirects=False,
        )

        self.assertEqual(verify_response.status_code, 302)
        self.assertIn(f"/reset-password/{token}", verify_response.headers.get("Location", ""))

        response = self.client.post(
            f"/reset-password/{token}",
            data={
                "password": "newsecret123",
                "confirm_password": "newsecret123",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"password changed successfully", response.data.lower())

        with app_module.app.app_context():
            updated_user = app_module.User.query.filter_by(email="resetter@example.com").first()
            updated_record = app_module.PasswordResetToken.query.filter_by(token=token).first()

        self.assertTrue(app_module.bcrypt.check_password_hash(updated_user.password, "newsecret123"))
        self.assertTrue(updated_record.used)

        reset_again_response = self.client.get(f"/reset-password/{token}", follow_redirects=True)
        self.assertEqual(reset_again_response.status_code, 200)
        self.assertIn(b"invalid or has expired", reset_again_response.data.lower())

        old_password_login = self.client.post(
            "/login",
            data={"email": "resetter@example.com", "password": "secret123"},
            follow_redirects=True,
        )
        self.assertIn(b"invalid email or password", old_password_login.data.lower())

        new_password_login = self.client.post(
            "/login",
            data={"email": "resetter@example.com", "password": "newsecret123"},
            follow_redirects=True,
        )
        self.assertIn(b"dashboard", new_password_login.data.lower())

    @patch("app.smtplib.SMTP", FakeSMTP)
    def test_email_reset_link_still_works_as_alternative(self):
        with app_module.app.app_context():
            user = app_module.User.query.filter_by(email="resetter@example.com").first()
            token = app_module.create_password_reset_token(user)

        response = self.client.post(
            f"/reset-password/{token}",
            data={
                "password": "altnewsecret123",
                "confirm_password": "altnewsecret123",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"password changed successfully", response.data.lower())

    def test_verify_code_rejects_expired_code(self):
        with app_module.app.app_context():
            user = app_module.User.query.filter_by(email="resetter@example.com").first()
            app_module.create_password_reset_token(user)
            record = app_module.PasswordResetToken.query.filter_by(user_id=user.id).first()
            # Strip timezone when setting expires_at for SQLite (it stores naive datetimes)
            record.expires_at = (app_module._now_utc() - app_module.timedelta(minutes=1)).replace(tzinfo=None)
            app_module.db.session.commit()
            user_id = user.id
            record_code = record.code

        with self.client.session_transaction() as test_session:
            test_session["password_reset_user_id"] = user_id

        response = self.client.post(
            "/verify-reset-code",
            data={"code": record_code},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"invalid or has expired", response.data.lower())

    def test_reset_password_rejects_expired_token(self):
        with app_module.app.app_context():
            user = app_module.User.query.filter_by(email="resetter@example.com").first()
            token = app_module.create_password_reset_token(user)
            record = app_module.PasswordResetToken.query.filter_by(token=token).first()
            # Strip timezone when setting expires_at for SQLite (it stores naive datetimes)
            record.expires_at = (app_module._now_utc() - app_module.timedelta(minutes=1)).replace(tzinfo=None)
            app_module.db.session.commit()

        response = self.client.get(f"/reset-password/{token}", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"invalid or has expired", response.data.lower())

    @patch("app.smtplib.SMTP", side_effect=RuntimeError("smtp offline"))
    def test_forgot_password_shows_error_when_email_send_fails(self, _smtp):
        response = self.client.post("/forgot-password", data={"email": "resetter@example.com"}, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"could not send the reset email", response.data.lower())


if __name__ == "__main__":
    unittest.main()
