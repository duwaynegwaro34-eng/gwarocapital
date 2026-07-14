import os

try:
	from dotenv import load_dotenv
	load_dotenv()
except ImportError:
	pass  # dotenv not available, continue without it


def _to_bool(value, default=False):
	if value is None:
		return default
	return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
	def __init__(self):
		self.secret_key = os.getenv("SECRET_KEY", "gwaro-capital-secret-key")
		self.database_uri = os.getenv("DATABASE_URL", "sqlite:///gwaro.db")
		self.debug = _to_bool(os.getenv("FLASK_DEBUG"), default=True)
		self.testing = _to_bool(os.getenv("TESTING"), default=False)
		self.developer_mt5_accounts = {
			acct.strip()
			for acct in os.getenv("DEVELOPER_MT5_ACCOUNTS", "").split(",")
			if acct.strip()
		}

		self.session_cookie_secure = _to_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False)
		self.session_cookie_httponly = _to_bool(os.getenv("SESSION_COOKIE_HTTPONLY"), default=True)
		self.session_cookie_samesite = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
		self.permanent_session_lifetime_minutes = int(os.getenv("PERMANENT_SESSION_LIFETIME_MINUTES", "120"))

		self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
		self.log_file = os.getenv("LOG_FILE", "logs/gwaro_app.log")
		self.backup_dir = os.getenv("BACKUP_DIR", "database/backups")
		self.mt5_experts_path = os.getenv("MT5_EXPERTS_PATH", r"C:\Users\Deca\AppData\Roaming\MetaQuotes\Terminal\E7DB6AF1FE93F292652A5D3B98342601\MQL5\Experts\Advisors")
		self.mt5_bridge_dir = os.getenv(
			"MT5_BRIDGE_DIR",
			os.path.join(
				os.path.expanduser("~"),
				"AppData",
				"Roaming",
				"MetaQuotes",
				"Terminal",
				"E7DB6AF1FE93F292652A5D3B98342601",
				"MQL5",
				"Files",
				"gwaro_mt5_bridge",
			),
		)

		self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
		self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
		self.smtp_username = os.getenv("SMTP_USERNAME", "gwaroduwayne@gmail.com")
		self.smtp_password = os.getenv("SMTP_PASSWORD", "")
		self.smtp_use_tls = _to_bool(os.getenv("SMTP_USE_TLS"), default=True)
		self.smtp_use_ssl = _to_bool(os.getenv("SMTP_USE_SSL"), default=False)
		self.smtp_timeout_seconds = int(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
		self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "gwaroduwayne@gmail.com")
		self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "GWARO Capital")
		self.password_reset_expiry_minutes = int(os.getenv("PASSWORD_RESET_EXPIRY_MINUTES", "30"))

		self.login_rate_limit_window_seconds = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))
		self.login_rate_limit_attempts = int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5"))
		self.login_lockout_seconds = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "600"))

		self.admin_emails = {
			email.strip().lower()
			for email in os.getenv("ADMIN_EMAILS", "").split(",")
			if email.strip()
		}


settings = Settings()
