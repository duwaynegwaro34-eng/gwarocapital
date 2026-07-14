from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask import send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from functools import wraps
from collections import defaultdict
from io import BytesIO, StringIO
try:
    from flask_bcrypt import Bcrypt
except ImportError:
    from werkzeug.security import generate_password_hash as wz_generate_password_hash
    from werkzeug.security import check_password_hash as wz_check_password_hash

    class Bcrypt:
        def __init__(self, app=None):
            self.app = app

        def generate_password_hash(self, password):
            return wz_generate_password_hash(password).encode("utf-8")

        def check_password_hash(self, password_hash, password):
            return wz_check_password_hash(password_hash, password)

from werkzeug.security import check_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, inspect
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
import re
import os
import uuid
import hashlib
import json
import csv
import zipfile
import logging
from logging.handlers import RotatingFileHandler
from xml.sax.saxutils import escape as xml_escape
from pathlib import Path
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
import bot as trading_bot
import threading
import time
from services.bot_manager import BotManager
from services.payment_service import PaymentService
from services.backup_service import BackupService
from mt5_manager import mt5_manager
from config import settings as app_settings

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = app_settings.database_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = app_settings.secret_key
app.config["SESSION_COOKIE_SECURE"] = app_settings.session_cookie_secure
app.config["SESSION_COOKIE_HTTPONLY"] = app_settings.session_cookie_httponly
app.config["SESSION_COOKIE_SAMESITE"] = app_settings.session_cookie_samesite
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=app_settings.permanent_session_lifetime_minutes)

os.makedirs(os.path.dirname(app_settings.log_file), exist_ok=True)
file_handler = RotatingFileHandler(app_settings.log_file, maxBytes=1024 * 1024, backupCount=3)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
app.logger.setLevel(getattr(logging, app_settings.log_level, logging.INFO))
app.logger.addHandler(file_handler)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access your dashboard."
login_manager.session_protection = "strong"

# Expose sitemap and robots at site root so crawlers can fetch them directly
@app.route('/robots.txt')
def robots_txt():
    return send_file(os.path.join(app.root_path, 'robots.txt'), mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    return send_file(os.path.join(app.root_path, 'sitemap.xml'), mimetype='application/xml')


# Helper function for timezone-aware datetime defaults in models
def _utc_now():
    """Return current UTC time as timezone-aware datetime"""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    mt5_account = db.Column(db.String(50))
    mt5_server = db.Column(db.String(100))
    mt5_name = db.Column(db.String(100))
    mt5_connected = db.Column(db.Boolean, default=False)


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", backref=db.backref("password_reset_tokens", lazy=True))


class TradeJournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    journal_event_id = db.Column(db.String(255), unique=True, nullable=False)
    ticket = db.Column(db.String(50), nullable=True)
    symbol = db.Column(db.String(50), nullable=False)
    entry_price = db.Column(db.Float, nullable=True)
    exit_price = db.Column(db.Float, nullable=True)
    profit_loss = db.Column(db.Float, default=0.0, nullable=False)
    open_time = db.Column(db.DateTime, nullable=True)
    close_time = db.Column(db.DateTime, nullable=True)
    strategy_bot = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="OPEN", nullable=False)


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    plan_name = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default="ACTIVE", nullable=False)
    start_date = db.Column(db.DateTime, default=_utc_now, nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=True)
    auto_renew = db.Column(db.Boolean, default=True, nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)


class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    license_key = db.Column(db.String(64), unique=True, nullable=False)
    mt5_account = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), default="ACTIVE", nullable=False)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    activated_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)


class PaymentTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    provider = db.Column(db.String(20), nullable=False)
    reference = db.Column(db.String(80), unique=True, nullable=False)
    plan_name = db.Column(db.String(30), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    status = db.Column(db.String(20), default="PENDING", nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)


class AdminRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(120), nullable=False)
    target = db.Column(db.String(120), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)


class BotSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bot_id = db.Column(db.String(100), nullable=False)
    mt5_account = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(30), default="STOPPED", nullable=False)
    started_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    stopped_at = db.Column(db.DateTime, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)

    user = db.relationship("User", backref=db.backref("bot_sessions", lazy=True))


class BotActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("bot_session.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    type = db.Column(db.String(60), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)

    session = db.relationship("BotSession", backref=db.backref("activities", lazy=True))
    user = db.relationship("User", backref=db.backref("bot_activity_logs", lazy=True))


RISK_LIMIT_PERCENT = 2.0
LARGE_PROFIT_THRESHOLD = 100.0
LARGE_LOSS_THRESHOLD = -100.0

PLAN_MONTHLY = "MONTHLY"
PLAN_LIFETIME = "LIFETIME"
PLAN_PRICING = {
    PLAN_MONTHLY: 50.0,
    PLAN_LIFETIME: 250.0,
}

_NOTIFICATION_STATE = {
    "seen_event_ids": set(),
    "last_mt5_connected": None,
}

_LOGIN_ATTEMPTS = {}


bot_manager = BotManager(trading_bot)


def log_discovered_bots_on_startup():
    try:
        discovered = bot_manager.discover_available_bots()
        for bot in discovered:
            app.logger.info("Discovered MT5 EA at startup: %s", bot["name"])
    except Exception as exc:
        app.logger.exception("Failed to log discovered MT5 EAs: %s", exc)


log_discovered_bots_on_startup()
payment_service = PaymentService()
backup_service = BackupService(app_settings.backup_dir)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def verify_password(stored_password, provided_password):
    if not stored_password:
        return False

    if stored_password.startswith("$2"):
        return bcrypt.check_password_hash(stored_password, provided_password)

    if stored_password.startswith("pbkdf2") or stored_password.startswith("scrypt") or stored_password.startswith("argon2"):
        try:
            return check_password_hash(stored_password, provided_password)
        except ValueError:
            return False

    return stored_password == provided_password


def get_current_user():
    return current_user if current_user.is_authenticated else None


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _now_utc():
    return datetime.now(timezone.utc)


def _generate_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _csrf_valid():
    if app.testing:
        return True
    expected = session.get("csrf_token")
    provided = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    return bool(expected and provided and secrets.compare_digest(expected, provided))


def require_csrf():
    if _csrf_valid():
        return None

    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "CSRF token missing or invalid."}), 403

    flash("Security token expired. Please retry.", "error")
    return redirect(request.url)


@app.context_processor
def inject_security_context():
    return {
        "csrf_token": _generate_csrf_token(),
    }


def log_audit(action, target=None, details=None, user_id=None):
    try:
        effective_user_id = user_id
        if effective_user_id is None and current_user.is_authenticated:
            effective_user_id = current_user.id

        row = AuditLog(
            user_id=effective_user_id,
            action=action,
            target=target,
            ip_address=_client_ip(),
            details=details,
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to write audit log")


def is_admin_user(user):
    if not user:
        return False
    if user.email and user.email.lower() in app_settings.admin_emails:
        return True
    role = AdminRole.query.filter_by(user_id=user.id, is_active=True).first()
    return role is not None


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not is_admin_user(user):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "message": "Admin access required."}), 403
            return redirect(url_for("dashboard"))
        return func(*args, **kwargs)
    return wrapper


def _login_rate_key(email):
    return f"{_client_ip()}::{(email or '').strip().lower()}"


def login_rate_limited(email):
    key = _login_rate_key(email)
    now = _now_utc()
    data = _LOGIN_ATTEMPTS.get(key) or {
        "attempts": [],
        "blocked_until": None,
    }

    blocked_until = data.get("blocked_until")
    if blocked_until and now < blocked_until:
        return True, int((blocked_until - now).total_seconds())

    window_start = now - timedelta(seconds=app_settings.login_rate_limit_window_seconds)
    attempts = [ts for ts in data.get("attempts", []) if ts >= window_start]
    data["attempts"] = attempts
    data["blocked_until"] = None
    _LOGIN_ATTEMPTS[key] = data
    return False, 0


def record_login_attempt(email, success):
    key = _login_rate_key(email)
    now = _now_utc()
    data = _LOGIN_ATTEMPTS.get(key) or {
        "attempts": [],
        "blocked_until": None,
    }

    if success:
        _LOGIN_ATTEMPTS.pop(key, None)
        return

    window_start = now - timedelta(seconds=app_settings.login_rate_limit_window_seconds)
    attempts = [ts for ts in data.get("attempts", []) if ts >= window_start]
    attempts.append(now)
    data["attempts"] = attempts

    if len(attempts) >= app_settings.login_rate_limit_attempts:
        data["blocked_until"] = now + timedelta(seconds=app_settings.login_lockout_seconds)

    _LOGIN_ATTEMPTS[key] = data


def get_active_subscription(user_id):
    subscription = Subscription.query.filter_by(user_id=user_id).order_by(Subscription.id.desc()).first()
    if not subscription:
        return None

    if subscription.status == "ACTIVE" and subscription.expiry_date and subscription.expiry_date < _now_utc().replace(tzinfo=None):
        subscription.status = "EXPIRED"
        db.session.commit()

    return subscription


def subscription_status_payload(user):
    subscription = get_active_subscription(user.id)
    if not subscription:
        return {
            "plan": None,
            "status": "EXPIRED",
            "start_date": None,
            "expiry_date": None,
            "is_active": False,
        }

    return {
        "plan": subscription.plan_name,
        "status": subscription.status,
        "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
        "expiry_date": subscription.expiry_date.isoformat() if subscription.expiry_date else None,
        "is_active": subscription.status == "ACTIVE",
    }


def generate_license_key(user_id, mt5_account):
    raw = f"{user_id}:{mt5_account}:{uuid.uuid4().hex}:{secrets.token_hex(16)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return f"GWC-{digest[:8]}-{digest[8:16]}-{digest[16:24]}"


def get_user_license(user, mt5_account):
    return License.query.filter_by(user_id=user.id, mt5_account=str(mt5_account)).first()


def _is_developer_mt5_account(mt5_account):
    """Return True for MT5 accounts configured as temporary developer bypass accounts."""
    return str(mt5_account).strip() in app_settings.developer_mt5_accounts


# TEMPORARY DEVELOPMENT BYPASS - REMOVE BEFORE PRODUCTION.
def _subscription_allows_license(user):
    sub = get_active_subscription(user.id)
    return bool(sub and sub.status == "ACTIVE")


def validate_license_for_bot_start(user):
    if not user:
        return False, "Login required"

    mt5_status = get_mt5_terminal_status()
    # In testing use the user's stored MT5 account to avoid depending on a local terminal
    if app.testing:
        mt5_account = user.mt5_account
    else:
        mt5_account = mt5_status.get("account_login") or user.mt5_account
    if not mt5_account:
        return False, "No MT5 account linked for licensing"

    license_row = get_user_license(user, mt5_account)
    if not license_row:
        if _is_developer_mt5_account(mt5_account):
            return True, "Developer Mode: License check bypassed."
        return False, "No license found for this MT5 account"

    if license_row.status != "ACTIVE":
        return False, f"License status is {license_row.status}"

    if license_row.expires_at and license_row.expires_at < _now_utc().replace(tzinfo=None):
        license_row.status = "EXPIRED"
        db.session.commit()
        return False, "License expired"

    if not _subscription_allows_license(user):
        return False, "Active subscription required"

    return True, "License valid"


def get_system_health():
    db_ok = True
    db_error = ""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    mt5_status = get_mt5_terminal_status()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": {"ok": db_ok, "error": db_error},
        "mt5": mt5_status,
        "timestamp": _now_utc().isoformat(),
    }


def create_password_reset_token(user):
    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = _now_utc() + timedelta(minutes=app_settings.password_reset_expiry_minutes)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        code=code,
        expires_at=expires_at,
    )
    db.session.add(reset_token)
    db.session.commit()
    return token


def send_password_reset_email(user, code, token):
    reset_link = url_for("reset_password", token=token, _external=True)
    msg = EmailMessage()
    msg["Subject"] = "Gwaro Capital Password Reset"
    msg["From"] = f"{app_settings.smtp_from_name} <{app_settings.smtp_from_email}>"
    msg["To"] = user.email

    text_body = render_template(
        "emails/password_reset_email.txt",
        user=user,
        code=code,
        reset_link=reset_link,
        expiry_minutes=app_settings.password_reset_expiry_minutes,
    )
    html_body = render_template(
        "emails/password_reset_email.html",
        user=user,
        code=code,
        reset_link=reset_link,
        expiry_minutes=app_settings.password_reset_expiry_minutes,
    )
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        smtp_class = smtplib.SMTP_SSL if app_settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(
            app_settings.smtp_host,
            app_settings.smtp_port,
            timeout=app_settings.smtp_timeout_seconds,
        ) as smtp:
            if not app_settings.smtp_use_ssl and app_settings.smtp_use_tls:
                smtp.starttls()
            if app_settings.smtp_username:
                smtp.login(app_settings.smtp_username, app_settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        app.logger.exception("Failed to send password reset email", extra={"target_email": user.email})
        return False

    return True


def _shutdown_mt5():
    mt5_manager.shutdown_client()


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_timestamp(value):
    if not value or value == "--":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_id(event):
    event_type = event.get("type", "")
    event_time = event.get("time", "")
    ticket = str(event.get("ticket") or "")
    message = event.get("message", "")
    return f"{event_type}:{event_time}:{ticket}:{message}"


def _extract_ticket_from_message(message):
    if not message:
        return None
    match = re.search(r"#(\d+)", message)
    return match.group(1) if match else None


def _sync_trading_journal():
    bot_state = bot_manager.status()
    activity_log = bot_state.get("activity_log", [])
    current_bot = bot_state.get("current_bot", "Unknown Bot")

    if not activity_log:
        return

    # Process oldest-to-newest so open/close sequences stay consistent.
    for event in reversed(activity_log):
        event_type = event.get("type", "")
        if event_type not in {"Trade Opened", "Trade Closed"}:
            continue

        event_key = _event_id(event)
        exists = TradeJournalEntry.query.filter_by(journal_event_id=event_key).first()
        if exists:
            continue

        ticket = str(event.get("ticket") or _extract_ticket_from_message(event.get("message", "")) or "")
        symbol = event.get("symbol") or "UNKNOWN"
        strategy_bot = event.get("bot") or current_bot
        event_time = _parse_iso_timestamp(event.get("time"))
        entry_price = _safe_float(event.get("entry_price"), None) if event.get("entry_price") is not None else None
        close_price = _safe_float(event.get("exit_price"), None) if event.get("exit_price") is not None else None
        profit = _safe_float(event.get("profit"), 0.0)

        if event_type == "Trade Opened":
            entry = TradeJournalEntry(
                journal_event_id=event_key,
                ticket=ticket,
                symbol=symbol,
                entry_price=entry_price,
                exit_price=None,
                profit_loss=0.0,
                open_time=event_time,
                close_time=None,
                strategy_bot=strategy_bot,
                status="OPEN",
            )
            db.session.add(entry)
        else:
            open_entry = None
            if ticket:
                open_entry = TradeJournalEntry.query.filter_by(ticket=ticket, status="OPEN").order_by(TradeJournalEntry.id.desc()).first()

            close_marker = TradeJournalEntry(
                journal_event_id=event_key,
                ticket=ticket,
                symbol=symbol,
                entry_price=open_entry.entry_price if open_entry else entry_price,
                exit_price=close_price,
                profit_loss=profit,
                open_time=open_entry.open_time if open_entry else None,
                close_time=event_time,
                strategy_bot=strategy_bot,
                status="CLOSED",
            )
            db.session.add(close_marker)

    db.session.commit()


def get_ai_trade_analysis():
    positions = get_mt5_positions()
    signals = {item.get("symbol"): item for item in generate_signals()}
    analysis = []

    for position in positions:
        symbol = position.get("symbol", "")
        side = position.get("type", "BUY")
        profit = _safe_float(position.get("profit"), 0.0)
        signal = signals.get(symbol)

        recommendation = "HOLD"
        confidence = 55
        reason = "No high-confidence directional conflict detected."

        if signal:
            signal_side = signal.get("signal", "HOLD")
            signal_conf = int(signal.get("confidence", 55))
            if signal_side == side and profit < 0:
                recommendation = "HOLD"
                confidence = max(60, signal_conf)
                reason = "Signal aligns with position direction; temporary drawdown suggests patience."
            elif signal_side != side and profit < 0:
                recommendation = signal_side
                confidence = max(65, signal_conf)
                reason = "Signal direction disagrees with losing position; consider rotating to trend."
            elif signal_side != side and profit >= 0:
                recommendation = "HOLD"
                confidence = max(58, signal_conf - 5)
                reason = "Position is profitable despite signal divergence; lock gains and monitor momentum."
            else:
                recommendation = signal_side
                confidence = max(60, signal_conf)
                reason = "Signal and current exposure align with short-term price structure."
        elif profit < 0:
            recommendation = "HOLD"
            confidence = 52
            reason = "Limited signal context; hold until stronger confirmation appears."

        analysis.append({
            "ticket": position.get("ticket"),
            "symbol": symbol,
            "position_type": side,
            "recommendation": recommendation,
            "confidence": confidence,
            "reason": reason,
            "profit": round(profit, 2),
        })

    return analysis


def get_risk_manager_summary():
    account = get_mt5_summary()
    positions = get_mt5_positions()
    balance = max(_safe_float(account.get("balance"), 0.0), 0.0)

    recommended_lot = max(0.01, round(balance * 0.00002, 2)) if balance > 0 else 0.01
    total_volume = sum(_safe_float(position.get("volume"), 0.0) for position in positions)
    estimated_risk = round(((total_volume * 1000.0) / balance) * 100, 2) if balance > 0 else 0.0
    exceeds_limit = estimated_risk > RISK_LIMIT_PERCENT

    warning = "Risk is within configured limits."
    if exceeds_limit:
        warning = f"Risk alert: {estimated_risk}% exceeds configured limit of {RISK_LIMIT_PERCENT}%."

    return {
        "recommended_lot_size": recommended_lot,
        "current_risk_percent": estimated_risk,
        "risk_limit_percent": RISK_LIMIT_PERCENT,
        "risk_exceeded": exceeds_limit,
        "warning": warning,
    }


def _compute_performance_from_entries(entries):
    total_trades = len(entries)
    wins = [entry for entry in entries if _safe_float(entry.profit_loss) > 0]
    losses = [entry for entry in entries if _safe_float(entry.profit_loss) < 0]

    winning_trades = len(wins)
    losing_trades = len(losses)
    win_rate = round((winning_trades / total_trades) * 100, 2) if total_trades else 0.0
    net_profit = round(sum(_safe_float(entry.profit_loss) for entry in entries), 2)

    gross_profit = sum(_safe_float(entry.profit_loss) for entry in wins)
    gross_loss = abs(sum(_safe_float(entry.profit_loss) for entry in losses))
    profit_factor = round((gross_profit / gross_loss), 2) if gross_loss > 0 else round(gross_profit, 2)

    running = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for entry in sorted(entries, key=lambda item: item.close_time or datetime.min):
        running += _safe_float(entry.profit_loss)
        peak = max(peak, running)
        drawdown = peak - running
        max_drawdown = max(max_drawdown, drawdown)

    return {
        "win_rate": win_rate,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "net_profit": net_profit,
        "profit_factor": profit_factor,
        "maximum_drawdown": round(max_drawdown, 2),
    }


def get_performance_summary():
    _sync_trading_journal()
    entries = TradeJournalEntry.query.filter_by(status="CLOSED").all()
    performance = _compute_performance_from_entries(entries)
    metrics = get_analytics_performance_summary()
    performance.update({
        "today_profit_loss": metrics["today_profit_loss"],
        "weekly_profit_loss": metrics["weekly_profit_loss"],
        "monthly_profit_loss": metrics["monthly_profit_loss"],
        "average_profit_per_trade": metrics["average_profit_per_trade"],
        "average_loss_per_trade": metrics["average_loss_per_trade"],
        "current_drawdown": metrics["current_drawdown"],
        "floating_profit_loss": metrics["floating_profit_loss"],
        "roi_percent": metrics["roi_percent"],
    })
    return performance


def get_todays_performance_summary():
    _sync_trading_journal()
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    entries = TradeJournalEntry.query.filter(
        TradeJournalEntry.status == "CLOSED",
        TradeJournalEntry.close_time != None,
        TradeJournalEntry.close_time >= start_of_day,
    ).all()
    result = _compute_performance_from_entries(entries)
    result["date"] = start_of_day.date().isoformat()
    return result


def get_trading_journal(start_date=None, end_date=None, bot=None):
    _sync_trading_journal()
    query = TradeJournalEntry.query.order_by(TradeJournalEntry.id.desc())

    if bot:
        query = query.filter(TradeJournalEntry.strategy_bot == bot)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(
                db.or_(
                    TradeJournalEntry.open_time >= start_dt,
                    TradeJournalEntry.close_time >= start_dt,
                )
            )
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(
                db.or_(
                    TradeJournalEntry.open_time < end_dt,
                    TradeJournalEntry.close_time < end_dt,
                )
            )
        except ValueError:
            pass

    items = []
    for entry in query.limit(200).all():
        items.append({
            "ticket": entry.ticket,
            "symbol": entry.symbol,
            "entry": entry.entry_price,
            "exit": entry.exit_price,
            "profit_loss": round(_safe_float(entry.profit_loss), 2),
            "open_time": entry.open_time.isoformat() if entry.open_time else "--",
            "close_time": entry.close_time.isoformat() if entry.close_time else "--",
            "bot": entry.strategy_bot,
            "status": entry.status,
        })

    return items


def _bot_display_name(bot_value):
    if not bot_value:
        return "--"
    return str(bot_value).strip()


def _bot_id_from_value(bot_value):
    if not bot_value:
        return ""
    return str(bot_value).strip()


def _format_duration(start_time, end_time=None):
    if not start_time:
        return "--"

    end_time = end_time or _now_utc()
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        return "--"

    delta = end_time - start_time
    total_seconds = max(int(delta.total_seconds()), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _format_trade_value(value, decimals=2):
    if value is None:
        return "--"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "--"


def _build_trade_lookup_tables():
    activity_index = {}
    for event in bot_manager.status().get("activity_log", []):
        ticket = str(event.get("ticket") or _extract_ticket_from_message(event.get("message", "")) or "").strip()
        if ticket and ticket not in activity_index:
            activity_index[ticket] = event

    position_index = {}
    for position in get_mt5_positions():
        ticket = str(position.get("ticket") or "").strip()
        if ticket:
            position_index[ticket] = position

    return activity_index, position_index


def _trade_row_from_entry(entry, activity_index=None, position_index=None):
    activity_index = activity_index or {}
    position_index = position_index or {}
    ticket = str(entry.ticket or "").strip()
    activity_event = activity_index.get(ticket, {})
    live_position = position_index.get(ticket, {})

    side = activity_event.get("position_type") or live_position.get("type") or "--"
    lot_size = activity_event.get("volume") if activity_event else live_position.get("volume")
    open_time = entry.open_time or _parse_iso_timestamp(activity_event.get("time"))
    close_time = entry.close_time
    is_open = str(entry.status).upper() == "OPEN"

    if is_open and live_position:
        current_price = live_position.get("current_price")
        exit_price = current_price
        profit_loss = live_position.get("profit", entry.profit_loss)
        close_time_value = "--"
        duration = _format_duration(open_time)
        status = "OPEN"
    else:
        exit_price = entry.exit_price
        profit_loss = entry.profit_loss
        close_time_value = close_time.isoformat() if close_time else "--"
        duration = _format_duration(open_time, close_time) if open_time and close_time else "--"
        status = "CLOSED" if close_time else str(entry.status or "OPEN")

    return {
        "ticket": ticket or "--",
        "symbol": entry.symbol,
        "side": side,
        "lot_size": _format_trade_value(lot_size, 2),
        "entry_price": _format_trade_value(entry.entry_price, 5),
        "exit_price": _format_trade_value(exit_price, 5),
        "stop_loss": _format_trade_value(live_position.get("sl"), 5),
        "take_profit": _format_trade_value(live_position.get("tp"), 5),
        "profit_loss": round(_safe_float(profit_loss), 2),
        "open_time": open_time.isoformat() if isinstance(open_time, datetime) else (open_time or "--"),
        "close_time": close_time_value,
        "duration": duration,
        "bot_used": _bot_display_name(entry.strategy_bot),
        "status": status,
    }


def _collect_trade_rows(start_date=None, end_date=None, bot=None, symbol=None, search=None, include_open=True):
    _sync_trading_journal()
    query = TradeJournalEntry.query.order_by(TradeJournalEntry.close_time.desc().nullslast(), TradeJournalEntry.id.desc())

    if bot:
        query = query.filter(TradeJournalEntry.strategy_bot == bot)

    if symbol:
        query = query.filter(TradeJournalEntry.symbol == symbol)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(
                db.or_(
                    TradeJournalEntry.open_time >= start_dt,
                    TradeJournalEntry.close_time >= start_dt,
                )
            )
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(
                db.or_(
                    TradeJournalEntry.open_time < end_dt,
                    TradeJournalEntry.close_time < end_dt,
                )
            )
        except ValueError:
            pass

    activity_index, position_index = _build_trade_lookup_tables()
    rows = []
    search_text = (search or "").strip().lower()

    for entry in query.limit(500).all():
        if not include_open and str(entry.status).upper() == "OPEN":
            continue

        row = _trade_row_from_entry(entry, activity_index=activity_index, position_index=position_index)

        if search_text:
            haystack = " ".join(str(row.get(key, "")) for key in ("ticket", "symbol", "side", "bot_used", "status")).lower()
            if search_text not in haystack:
                continue

        rows.append(row)

    return rows


def _paginate_rows(rows, page=1, per_page=20):
    page = max(int(page or 1), 1)
    per_page = min(max(int(per_page or 20), 1), 100)
    total = len(rows)
    start = (page - 1) * per_page
    end = start + per_page
    items = rows[start:end]
    total_pages = max((total + per_page - 1) // per_page, 1)
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def _trade_rows_for_export(params):
    return _collect_trade_rows(
        start_date=params.get("start_date"),
        end_date=params.get("end_date"),
        bot=params.get("bot"),
        symbol=params.get("symbol"),
        search=params.get("search"),
        include_open=True,
    )


def _trade_rows_to_csv(rows):
    output = StringIO()
    writer = csv.writer(output)
    headers = [
        "Ticket", "Symbol", "Buy/Sell", "Lot Size", "Entry Price", "Exit Price",
        "Stop Loss", "Take Profit", "Profit/Loss", "Open Time", "Close Time", "Duration", "Bot Used",
    ]
    writer.writerow(headers)
    for row in rows:
        writer.writerow([
            row["ticket"], row["symbol"], row["side"], row["lot_size"], row["entry_price"],
            row["exit_price"], row["stop_loss"], row["take_profit"], row["profit_loss"],
            row["open_time"], row["close_time"], row["duration"], row["bot_used"],
        ])
    return output.getvalue().encode("utf-8")


def _trade_rows_to_xlsx(rows):
    headers = [
        "Ticket", "Symbol", "Buy/Sell", "Lot Size", "Entry Price", "Exit Price",
        "Stop Loss", "Take Profit", "Profit/Loss", "Open Time", "Close Time", "Duration", "Bot Used",
    ]

    def _cell_ref(col_index, row_index):
        letters = ""
        col = col_index + 1
        while col:
            col, rem = divmod(col - 1, 26)
            letters = chr(65 + rem) + letters
        return f"{letters}{row_index}"

    sheet_rows = []
    all_rows = [headers] + [[
        row["ticket"], row["symbol"], row["side"], row["lot_size"], row["entry_price"],
        row["exit_price"], row["stop_loss"], row["take_profit"], row["profit_loss"],
        row["open_time"], row["close_time"], row["duration"], row["bot_used"],
    ] for row in rows]

    for row_index, row_values in enumerate(all_rows, start=1):
        cells = []
        for col_index, value in enumerate(row_values):
            cell_ref = _cell_ref(col_index, row_index)
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{xml_escape(str(value))}</t></is></c>'
            )
        sheet_rows.append(f"<row r=\"{row_index}\">{''.join(cells)}</row>")

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Trade History" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )

    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", root_rels)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    buffer.seek(0)
    return buffer


def _compute_timeframe_profit(entries, start_dt=None, end_dt=None):
    filtered = []
    for entry in entries:
        close_time = entry.close_time
        # Strip timezone from start_dt/end_dt if present (for SQLite naive datetime comparison)
        start_naive = start_dt.replace(tzinfo=None) if start_dt else None
        end_naive = end_dt.replace(tzinfo=None) if end_dt else None
        
        if start_naive and (not close_time or close_time < start_naive):
            continue
        if end_naive and (not close_time or close_time >= end_naive):
            continue
        filtered.append(entry)
    return round(sum(_safe_float(entry.profit_loss) for entry in filtered), 2)


def _build_trade_timeseries(entries, current_balance, current_equity):
    ordered = sorted(entries, key=lambda item: item.close_time or item.open_time or datetime.min)
    total_profit = round(sum(_safe_float(entry.profit_loss) for entry in ordered), 2)
    base_balance = round(_safe_float(current_balance) - total_profit, 2)
    base_equity = round(_safe_float(current_equity) - total_profit, 2)

    balance_curve = []
    equity_curve = []
    drawdown_curve = []
    win_rate_curve = []
    daily_profit = defaultdict(float)
    weekly_profit = defaultdict(float)
    monthly_profit = defaultdict(float)

    running_profit = 0.0
    wins = 0
    total = 0
    peak = 0.0

    for entry in ordered:
        if not entry.close_time:
            continue

        profit = _safe_float(entry.profit_loss)
        total += 1
        running_profit += profit
        if profit > 0:
            wins += 1

        close_time = entry.close_time
        balance_curve.append({
            "time": close_time.isoformat(),
            "value": round(base_balance + running_profit, 2),
        })
        equity_curve.append({
            "time": close_time.isoformat(),
            "value": round(base_equity + running_profit, 2),
        })
        peak = max(peak, running_profit)
        drawdown_curve.append({
            "time": close_time.isoformat(),
            "value": round(peak - running_profit, 2),
        })
        win_rate_curve.append({
            "time": close_time.isoformat(),
            "value": round((wins / total) * 100, 2) if total else 0.0,
        })

        daily_key = close_time.strftime("%Y-%m-%d")
        weekly_key = close_time.strftime("%Y-W%U")
        monthly_key = close_time.strftime("%Y-%m")
        daily_profit[daily_key] += profit
        weekly_profit[weekly_key] += profit
        monthly_profit[monthly_key] += profit

    return {
        "equity_curve": equity_curve,
        "balance_history": balance_curve,
        "drawdown_history": drawdown_curve,
        "win_rate_history": win_rate_curve,
        "daily_profit": [{"label": key, "value": round(value, 2)} for key, value in sorted(daily_profit.items())],
        "weekly_profit": [{"label": key, "value": round(value, 2)} for key, value in sorted(weekly_profit.items())],
        "monthly_profit": [{"label": key, "value": round(value, 2)} for key, value in sorted(monthly_profit.items())],
    }


def get_analytics_performance_summary():
    _sync_trading_journal()
    entries = TradeJournalEntry.query.filter(TradeJournalEntry.status == "CLOSED").all()
    performance = _compute_performance_from_entries(entries)
    current_mt5 = get_mt5_summary()
    now = _now_utc()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = now - timedelta(days=7)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    wins = [entry for entry in entries if _safe_float(entry.profit_loss) > 0]
    losses = [entry for entry in entries if _safe_float(entry.profit_loss) < 0]
    gross_profit = sum(_safe_float(entry.profit_loss) for entry in wins)
    gross_loss = abs(sum(_safe_float(entry.profit_loss) for entry in losses))
    current_dd = 0.0
    running = 0.0
    peak = 0.0
    for entry in sorted(entries, key=lambda item: item.close_time or datetime.min):
        running += _safe_float(entry.profit_loss)
        peak = max(peak, running)
        current_dd = peak - running

    total_trades = performance["total_trades"]
    average_profit = round(gross_profit / len(wins), 2) if wins else 0.0
    average_loss = round(gross_loss / len(losses), 2) if losses else 0.0
    net_profit = performance["net_profit"]
    balance = _safe_float(current_mt5.get("balance"), 0.0)
    roi = round((net_profit / max(balance - net_profit, 1.0)) * 100, 2) if balance else 0.0

    return {
        **performance,
        "today_profit_loss": _compute_timeframe_profit(entries, start_of_day, None),
        "weekly_profit_loss": _compute_timeframe_profit(entries, start_of_week, None),
        "monthly_profit_loss": _compute_timeframe_profit(entries, start_of_month, None),
        "average_profit_per_trade": average_profit,
        "average_loss_per_trade": average_loss,
        "current_drawdown": round(current_dd, 2),
        "floating_profit_loss": round(_safe_float(current_mt5.get("floating_profit"), 0.0), 2),
        "roi_percent": roi,
        "account_balance": round(balance, 2),
        "current_equity": round(_safe_float(current_mt5.get("equity"), 0.0), 2),
        "current_time": now.isoformat(),
    }


def get_bot_statistics():
    _sync_trading_journal()
    bot_state = bot_manager.status()
    active_bot_id = bot_state.get("current_bot_id")
    active_bot_name = bot_state.get("current_bot")
    open_positions = get_mt5_positions()
    entries = TradeJournalEntry.query.filter(TradeJournalEntry.status == "CLOSED").all()
    today = _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today_naive = today.replace(tzinfo=None)

    stats = []
    for bot in bot_manager.available_bots():
        bot_id = bot.get("id") or ""
        bot_name = bot.get("name") or bot_id
        bot_entries = [entry for entry in entries if _bot_display_name(entry.strategy_bot) == bot_name]
        total_trades = len(bot_entries)
        wins = [entry for entry in bot_entries if _safe_float(entry.profit_loss) > 0]
        losses = [entry for entry in bot_entries if _safe_float(entry.profit_loss) < 0]
        today_entries = [entry for entry in bot_entries if entry.close_time and entry.close_time >= today_naive]
        total_profit = round(sum(_safe_float(entry.profit_loss) for entry in bot_entries), 2)
        current_profit = total_profit
        if bot_id == active_bot_id and bot_state.get("running"):
            current_profit = round(total_profit + sum(_safe_float(position.get("profit"), 0.0) for position in open_positions), 2)

        latest_entry = max(bot_entries, key=lambda item: item.close_time or item.open_time or datetime.min, default=None)
        latest_activity = next((event for event in bot_state.get("activity_log", []) if _bot_display_name(event.get("bot", active_bot_id)) == bot_name), None)

        stats.append({
            "bot_id": bot_id,
            "bot_name": bot_name,
            "running": bool(bot_state.get("running") and active_bot_id == bot_id),
            "trades_today": len(today_entries),
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round((len(wins) / total_trades) * 100, 2) if total_trades else 0.0,
            "current_profit": current_profit,
            "total_profit": total_profit,
            "current_symbol": latest_entry.symbol if latest_entry else (open_positions[0].get("symbol") if open_positions else "--"),
            "current_timeframe": "M5",
            "last_trade_time": (latest_entry.close_time or latest_entry.open_time).isoformat() if latest_entry and (latest_entry.close_time or latest_entry.open_time) else "--",
            "last_signal": latest_activity.get("message", bot_state.get("last_signal", "--")) if latest_activity else bot_state.get("last_signal", "--") if bot_name == active_bot_name else "--",
            "last_execution_time": latest_activity.get("time") if latest_activity else bot_state.get("last_execution", "--") if bot_name == active_bot_name else "--",
        })

    best_bot = max(stats, key=lambda item: item["total_profit"], default=None)
    worst_bot = min(stats, key=lambda item: item["total_profit"], default=None)
    return {
        "items": stats,
        "best_bot": best_bot,
        "worst_bot": worst_bot,
        "active_bot": active_bot_name,
    }


def get_dashboard_summary():
    performance = get_analytics_performance_summary()
    bot_stats = get_bot_statistics()
    open_positions = get_mt5_positions()
    closed_today = _collect_trade_rows(include_open=False)
    current_mt5 = get_mt5_summary()

    today_str = _now_utc().date().isoformat()
    today_rows = [row for row in closed_today if row["close_time"] != "--" and row["close_time"][:10] == today_str]
    largest_win_today = max(today_rows, key=lambda item: item["profit_loss"], default=None)
    largest_loss_today = min(today_rows, key=lambda item: item["profit_loss"], default=None)
    active_sessions = len(open_positions) + (1 if bot_manager.status().get("running") else 0)

    return {
        "best_performing_bot": bot_stats.get("best_bot"),
        "worst_performing_bot": bot_stats.get("worst_bot"),
        "largest_win_today": largest_win_today,
        "largest_loss_today": largest_loss_today,
        "current_floating_profit": round(_safe_float(current_mt5.get("floating_profit"), 0.0), 2),
        "current_drawdown": performance.get("current_drawdown", 0.0),
        "open_positions": len(open_positions),
        "closed_trades_today": len(today_rows),
        "active_trading_sessions": active_sessions,
        "mt5_connection_health": get_mt5_terminal_status(),
        "performance": performance,
        "bot_statistics": bot_stats,
        "account_summary": current_mt5,
    }


def get_chart_data():
    _sync_trading_journal()
    entries = TradeJournalEntry.query.filter(TradeJournalEntry.status == "CLOSED").all()
    mt5_summary = get_mt5_summary()
    return _build_trade_timeseries(entries, mt5_summary.get("balance", 0.0), mt5_summary.get("equity", 0.0))


def get_trade_history_page(start_date=None, end_date=None, bot=None, symbol=None, search=None, page=1, per_page=20):
    rows = _collect_trade_rows(start_date=start_date, end_date=end_date, bot=bot, symbol=symbol, search=search, include_open=True)
    rows = sorted(rows, key=lambda item: item["close_time"] if item["close_time"] != "--" else item["open_time"], reverse=True)
    return _paginate_rows(rows, page=page, per_page=per_page)


def get_smart_notifications():
    notifications = []
    _sync_trading_journal()
    bot_state = bot_manager.status()
    activity_log = bot_state.get("activity_log", [])
    account = get_mt5_summary()
    performance = get_analytics_performance_summary()

    current_connected = bool(get_mt5_terminal_status().get("connected"))
    previous_connected = _NOTIFICATION_STATE.get("last_mt5_connected")
    if previous_connected is None:
        _NOTIFICATION_STATE["last_mt5_connected"] = current_connected
    elif previous_connected != current_connected:
        _NOTIFICATION_STATE["last_mt5_connected"] = current_connected
        notifications.append({
            "id": f"mt5-status:{int(current_connected)}:{datetime.now(timezone.utc).isoformat()}",
            "type": "MT5 Reconnected" if current_connected else "MT5 Disconnected",
            "message": "MT5 reconnected successfully." if current_connected else "MT5 disconnected from terminal.",
            "severity": "success" if current_connected else "error",
        })

    for event in reversed(activity_log):
        event_type = event.get("type", "")
        if event_type not in {"Bot Started", "Bot Stopped", "Trade Opened", "Trade Closed", "Errors"}:
            continue

        event_key = _event_id(event)
        if event_key in _NOTIFICATION_STATE["seen_event_ids"]:
            continue

        _NOTIFICATION_STATE["seen_event_ids"].add(event_key)
        severity = "info"
        notification_type = event_type
        profit = _safe_float(event.get("profit"), 0.0)
        if event_type in {"Bot Started", "Trade Opened"}:
            severity = "success"
        elif event_type in {"Bot Stopped", "Trade Closed"}:
            severity = "info"
        elif event_type == "Errors":
            severity = "error"

        if event_type == "Trade Closed":
            if profit > 0:
                severity = "success"
                notification_type = "Profit Booked"
            elif profit < 0:
                severity = "error"
                notification_type = "Loss Recorded"

        notifications.append({
            "id": event_key,
            "type": notification_type,
            "message": event.get("message", ""),
            "severity": severity,
        })

        if event_type == "Trade Closed" and profit >= LARGE_PROFIT_THRESHOLD:
            notifications.append({
                "id": f"large-profit:{event_key}",
                "type": "Large Profit",
                "message": f"Large profit captured: ${profit:.2f}",
                "severity": "success",
            })
        if event_type == "Trade Closed" and profit <= LARGE_LOSS_THRESHOLD:
            notifications.append({
                "id": f"large-loss:{event_key}",
                "type": "Large Loss",
                "message": f"Large loss detected: ${profit:.2f}",
                "severity": "error",
            })

    floating_profit = _safe_float(account.get("floating_profit"), 0.0)
    margin = _safe_float(account.get("margin"), 0.0)
    equity = max(_safe_float(account.get("equity"), 0.0), 1.0)
    margin_ratio = (margin / equity) * 100 if equity else 0.0

    if margin_ratio >= 60:
        notifications.append({
            "id": f"margin-warning:{int(margin_ratio)}",
            "type": "Margin Warning",
            "message": f"Margin usage is elevated at {margin_ratio:.2f}%.",
            "severity": "error",
        })

    if performance.get("today_profit_loss", 0.0) >= 250:
        notifications.append({
            "id": f"daily-target:{performance.get('today_profit_loss', 0.0)}",
            "type": "Daily Target Reached",
            "message": f"Daily target reached with ${performance.get('today_profit_loss', 0.0):.2f} profit.",
            "severity": "success",
        })

    if performance.get("today_profit_loss", 0.0) <= -250:
        notifications.append({
            "id": f"daily-loss-limit:{performance.get('today_profit_loss', 0.0)}",
            "type": "Daily Loss Limit Reached",
            "message": f"Daily loss limit reached at ${performance.get('today_profit_loss', 0.0):.2f}.",
            "severity": "error",
        })

    if floating_profit > 0 and floating_profit >= LARGE_PROFIT_THRESHOLD:
        notifications.append({
            "id": f"floating-profit:{floating_profit}",
            "type": "Large Profit",
            "message": f"Floating profit is now ${floating_profit:.2f}.",
            "severity": "success",
        })

    return notifications[-30:]


def get_assistant_summary():
    ai_analysis = get_ai_trade_analysis()
    risk = get_risk_manager_summary()
    performance = get_performance_summary()
    today = get_todays_performance_summary()
    bot_state = bot_manager.status()

    return {
        "ai_trade_analysis": ai_analysis,
        "ai_summary": {
            "open_trade_count": len(ai_analysis),
            "high_confidence_signals": len([item for item in ai_analysis if int(item.get("confidence", 0)) >= 70]),
            "hold_count": len([item for item in ai_analysis if item.get("recommendation") == "HOLD"]),
        },
        "risk_manager": risk,
        "performance": performance,
        "today_performance": today,
        "active_bot_summary": {
            "bot": bot_state.get("current_bot", "--"),
            "status": bot_state.get("status", "Stopped"),
            "uptime": bot_state.get("uptime", "00:00:00"),
            "last_signal": bot_state.get("last_signal", "--"),
        },
        "notifications": get_smart_notifications(),
    }


def _subscription_expiry_for_plan(plan_name):
    if plan_name == PLAN_MONTHLY:
        return _now_utc() + timedelta(days=30)
    return None


def ensure_license_for_current_mt5(user, plan_name):
    mt5_status = get_mt5_terminal_status()
    mt5_account = mt5_status.get("account_login") or user.mt5_account
    if not mt5_account:
        return None, "No MT5 account linked"

    # Prevent duplicate MT5 account licensing across different users
    existing_other = License.query.filter(License.mt5_account == str(mt5_account)).first()
    if existing_other and existing_other.user_id != user.id:
        return None, "MT5 account already licensed by another user"

    expires_at = _subscription_expiry_for_plan(plan_name)
    row = get_user_license(user, mt5_account)
    if row:
        row.status = "ACTIVE"
        row.activated_at = _now_utc()
        row.revoked_at = None
        row.expires_at = expires_at
        db.session.commit()
        return row, "License updated"

    row = License(
        user_id=user.id,
        license_key=generate_license_key(user.id, mt5_account),
        mt5_account=str(mt5_account),
        status="ACTIVE",
        activated_at=_now_utc(),
        expires_at=expires_at,
    )
    db.session.add(row)
    db.session.commit()
    return row, "License generated"


def create_or_update_subscription(user, plan_name):
    current = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.id.desc()).first()
    expiry = _subscription_expiry_for_plan(plan_name)
    if current:
        current.plan_name = plan_name
        current.status = "ACTIVE"
        current.start_date = _now_utc()
        current.expiry_date = expiry
        current.auto_renew = plan_name == PLAN_MONTHLY
        current.cancelled_at = None
        db.session.commit()
        return current

    current = Subscription(
        user_id=user.id,
        plan_name=plan_name,
        status="ACTIVE",
        start_date=_now_utc(),
        expiry_date=expiry,
        auto_renew=plan_name == PLAN_MONTHLY,
    )
    db.session.add(current)
    db.session.commit()
    return current


def admin_metrics_payload():
    total_users = User.query.count()
    active_subscriptions = Subscription.query.filter_by(status="ACTIVE").count()
    active_bots = 1 if bot_manager.status().get("running") else 0
    successful_payments = PaymentTransaction.query.filter_by(status="SUCCESS").all()
    revenue = round(sum(_safe_float(item.amount, 0.0) for item in successful_payments), 2)

    return {
        "total_users": total_users,
        "active_bots": active_bots,
        "active_subscriptions": active_subscriptions,
        "revenue_summary": {
            "currency": "USD",
            "total": revenue,
            "payments_count": len(successful_payments),
        },
        "system_health": get_system_health(),
    }


def _default_mt5_summary(status="Disconnected"):
    return {
        "status": status,
        "connected": False,
        "account": None,
        "account_name": "",
        "broker": "",
        "server": "",
        "balance": 0.0,
        "equity": 0.0,
        "profit": 0.0,
        "free_margin": 0.0,
        "margin": 0.0,
        "leverage": 0,
        "currency": "",
        "floating_profit": 0.0,
        "connection_status": "Disconnected",
    }


def get_mt5_terminal_status():
    return mt5_manager.connection_status()


def refresh_mt5_bridge_state():
    try:
        bot_manager._bridge.sync_from_terminal()
    except Exception:
        app.logger.exception("Failed to sync MT5 bridge state")


def get_mt5_summary():
    if mt5 is None:
        return _default_mt5_summary(status="Offline")

    try:
        if not mt5_manager.initialize_client():
            return _default_mt5_summary()

        account = mt5.account_info()
        if account is None:
            return _default_mt5_summary()

        return {
            "status": "Connected",
            "connected": True,
            "account": account.login,
            "account_name": getattr(account, "name", "") or "",
            "broker": getattr(account, "company", "") or "",
            "server": getattr(account, "server", "") or "",
            "balance": round(float(getattr(account, "balance", 0.0) or 0.0), 2),
            "equity": round(float(getattr(account, "equity", 0.0) or 0.0), 2),
            "profit": round(float(getattr(account, "profit", 0.0) or 0.0), 2),
            "free_margin": round(float(getattr(account, "margin_free", 0.0) or 0.0), 2),
            "margin": round(float(getattr(account, "margin", 0.0) or 0.0), 2),
            "leverage": int(getattr(account, "leverage", 0) or 0),
            "currency": getattr(account, "currency", "") or "",
            "floating_profit": round(float(getattr(account, "profit", 0.0) or 0.0), 2),
            "connection_status": "Connected",
        }
    except Exception:
        return _default_mt5_summary()


def get_mt5_positions():
    if mt5 is None:
        return []

    try:
        if not mt5_manager.initialize_client():
            return []

        positions = mt5.positions_get() or []
        data = []

        for position in positions:
            tick = mt5.symbol_info_tick(getattr(position, "symbol", ""))
            is_buy = getattr(position, "type", 1) == 0
            current_price_raw = getattr(tick, "bid", 0.0) if is_buy else getattr(tick, "ask", 0.0)
            current_price = round(float(current_price_raw or 0.0), 5) if tick else 0.0
            data.append({
                "ticket": getattr(position, "ticket", None),
                "symbol": getattr(position, "symbol", ""),
                "type": "BUY" if is_buy else "SELL",
                "volume": getattr(position, "volume", 0.0),
                "entry_price": round(float(getattr(position, "price_open", 0.0) or 0.0), 5),
                "current_price": current_price,
                "sl": round(float(getattr(position, "sl", 0.0) or 0.0), 5),
                "tp": round(float(getattr(position, "tp", 0.0) or 0.0), 5),
                "profit": round(float(getattr(position, "profit", 0.0) or 0.0), 2),
                "open_time": datetime.fromtimestamp(getattr(position, "time", 0)).isoformat() if getattr(position, "time", 0) else "",
            })

        return data
    except Exception:
        return []


def _get_live_symbols(limit=25):
    # Single market architecture - only return XAUUSD
    return ["XAUUSD"]


def get_mt5_history(limit=10):
    if mt5 is None:
        return []

    try:
        if not mt5_manager.initialize_client():
            return []

        end = datetime.now()
        start = end - timedelta(days=7)
        deals = mt5.history_deals_get(start, end) or []
        data = []

        for deal in deals[-limit:]:
            timestamp = getattr(deal, "time", 0)
            deal_time = datetime.fromtimestamp(timestamp).isoformat() if timestamp else ""
            price = round(float(getattr(deal, "price", 0.0) or 0.0), 5)
            data.append({
                "ticket": getattr(deal, "ticket", None),
                "symbol": getattr(deal, "symbol", ""),
                "type": "BUY" if getattr(deal, "type", 1) == 0 else "SELL",
                "volume": getattr(deal, "volume", 0.0),
                "profit": round(float(getattr(deal, "profit", 0.0) or 0.0), 2),
                "open_price": price,
                "close_price": price,
                "open_time": deal_time,
                "close_time": deal_time,
                "strategy_bot": getattr(deal, "comment", "N/A") or "N/A",
            })

        return data
    except Exception:
        return []


def get_mt5_orders():
    if mt5 is None:
        return []

    try:
        if not mt5_manager.initialize_client():
            return []

        orders = mt5.orders_get() or []
        data = []
        for order in orders:
            data.append({
                "ticket": getattr(order, "ticket", None),
                "symbol": getattr(order, "symbol", ""),
                "type": "BUY" if getattr(order, "type", 1) == 0 else "SELL",
                "volume": getattr(order, "volume", 0.0),
                "price": round(float(getattr(order, "price", 0.0) or 0.0), 5),
                "sl": round(float(getattr(order, "sl", 0.0) or 0.0), 5),
                "tp": round(float(getattr(order, "tp", 0.0) or 0.0), 5),
                "state": getattr(order, "state", "") or "",
            })
        return data
    except Exception:
        return []


def get_market_data():
    # Single market - only fetch XAUUSD
    data = []

    if mt5 is None:
        return data

    try:
        if not mt5_manager.initialize_client():
            return data

        symbol = "XAUUSD"
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            data.append({
                "symbol": symbol,
                "bid": round(float(getattr(tick, "bid", 0.0) or 0.0), 5),
                "ask": round(float(getattr(tick, "ask", 0.0) or 0.0), 5),
            })
    except Exception:
        return []

    return data


def generate_signals():
    # Single market - only generate signals for XAUUSD
    signals = []

    if mt5 is None:
        return signals

    try:
        if not mt5_manager.initialize_client():
            return signals

        symbol = "XAUUSD"
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 3)
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)

        if rates is None or len(rates) < 2 or tick is None or info is None:
            return signals

        last_close = float(rates[-1]["close"])
        prev_close = float(rates[-2]["close"])
        point = float(getattr(info, "point", 0.00001) or 0.00001)
        spread = abs(float(getattr(tick, "ask", 0.0) or 0.0) - float(getattr(tick, "bid", 0.0) or 0.0))
        move = abs(last_close - prev_close)

        direction = "BUY" if last_close >= prev_close else "SELL"
        entry = float(getattr(tick, "ask", 0.0) or 0.0) if direction == "BUY" else float(getattr(tick, "bid", 0.0) or 0.0)
        risk = max(move, spread * 2, point * 10)
        sl = entry - risk if direction == "BUY" else entry + risk
        tp = entry + (risk * 2) if direction == "BUY" else entry - (risk * 2)
        confidence = int(max(50, min(95, 50 + int((move / point) * 0.5))))

        signals.append({
            "symbol": symbol,
            "signal": direction,
            "entry": round(entry, 5),
            "sl": round(sl, 5),
            "tp": round(tp, 5),
            "confidence": confidence,
        })
    except Exception:
        return []

    return signals

    return signals
def bot_loop():
    while bot_manager.status()["running"]:

        print("Bot is running...")

        # EA trading logic goes here

        import time
        time.sleep(5)
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/positions")
def positions():
    return jsonify(get_mt5_positions())


@app.route("/api/mt5/account")
def mt5_account_api():
    return jsonify(get_mt5_summary())


@app.route("/api/mt5/summary")
def mt5_summary_api():
    return jsonify(get_mt5_summary())


@app.route("/api/mt5/positions")
def mt5_positions_api():
    return jsonify(get_mt5_positions())


@app.route("/api/mt5/status")
def mt5_status_api():
    return jsonify(get_mt5_terminal_status())


@app.route("/api/mt5/engine-status")
def mt5_engine_status_api():
    return jsonify({
        "ok": True,
        "status": get_mt5_terminal_status(),
    })


@app.route("/api/mt5/connect", methods=["POST"])
def mt5_connect_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    login = payload.get("login", "")
    password = payload.get("password", "")
    server = payload.get("server", "")

    result = mt5_manager.connect(login, password, server)
    log_audit("mt5_connect_attempt", target=str(login), details=json.dumps({"ok": bool(result.get("ok"))}))
    return jsonify({
        **result,
        "status": mt5_manager.connection_status(),
    })


@app.route("/api/mt5/disconnect", methods=["POST"])
def mt5_disconnect_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    result = mt5_manager.disconnect()
    log_audit("mt5_disconnect", details=json.dumps({"ok": bool(result.get("ok"))}))
    return jsonify({
        **result,
        "status": mt5_manager.connection_status(),
    })


@app.route("/api/mt5/history")
def mt5_history_api():
    return jsonify(get_mt5_history())


@app.route("/api/mt5/trades")
def mt5_trades_api():
    return jsonify(get_mt5_history())


@app.route("/api/mt5/orders")
def mt5_orders_api():
    return jsonify(get_mt5_orders())


@app.route("/api/ai/analysis")
@login_required
def ai_trade_analysis_api():
    return jsonify({"analysis": get_ai_trade_analysis()})


@app.route("/api/risk/summary")
@login_required
def risk_summary_api():
    return jsonify(get_risk_manager_summary())


@app.route("/api/performance/summary")
@login_required
def performance_summary_api():
    return jsonify(get_performance_summary())


@app.route("/api/dashboard/account-summary")
@login_required
def dashboard_account_summary_api():
    return jsonify(get_mt5_summary())


@app.route("/api/dashboard/performance-summary")
@login_required
def dashboard_performance_summary_api():
    return jsonify(get_analytics_performance_summary())


@app.route("/api/dashboard/bot-statistics")
@login_required
def dashboard_bot_statistics_api():
    return jsonify(get_bot_statistics())


@app.route("/api/dashboard/trade-history")
@login_required
def dashboard_trade_history_api():
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 20)
    return jsonify(get_trade_history_page(
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
        bot=(request.args.get("bot") or "").strip() or None,
        symbol=(request.args.get("symbol") or "").strip() or None,
        search=(request.args.get("search") or "").strip() or None,
        page=page,
        per_page=per_page,
    ))


@app.route("/api/dashboard/equity-history")
@login_required
def dashboard_equity_history_api():
    return jsonify(get_chart_data())


@app.route("/api/dashboard/chart-data")
@login_required
def dashboard_chart_data_api():
    return jsonify(get_chart_data())


@app.route("/api/dashboard/summary")
@login_required
def dashboard_summary_api():
    return jsonify(get_dashboard_summary())


@app.route("/api/dashboard/notifications")
@login_required
def dashboard_notifications_api():
    return jsonify({"items": get_smart_notifications()})


@app.route("/api/dashboard/trade-history/export")
@login_required
def dashboard_trade_history_export_api():
    rows = _trade_rows_for_export(request.args)
    export_format = (request.args.get("format") or "csv").lower()

    if export_format == "excel":
        buffer = _trade_rows_to_xlsx(rows)
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="gwaro_trade_history.xlsx",
        )

    csv_bytes = _trade_rows_to_csv(rows)
    return send_file(
        BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name="gwaro_trade_history.csv",
    )


@app.route("/api/journal")
@login_required
def trading_journal_api():
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    bot = (request.args.get("bot") or "").strip() or None
    return jsonify({"items": get_trading_journal(start_date=start_date, end_date=end_date, bot=bot)})


@app.route("/api/notifications")
@login_required
def notifications_api():
    return jsonify({"items": get_smart_notifications()})


@app.route("/api/assistant/summary")
@login_required
def assistant_summary_api():
    return jsonify(get_assistant_summary())


@app.route("/health")
def health_check():
    health = get_system_health()
    code = 200 if health.get("status") == "ok" else 503
    return jsonify(health), code


@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self' https: 'unsafe-inline' 'unsafe-eval'"
    return response


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "Resource not found"}), 404
    return render_template("coming_soon.html", user=get_current_user(), title="Not Found", subtitle="The requested page does not exist"), 404


@app.errorhandler(500)
def handle_server_error(error):
    app.logger.exception("Unhandled server error")
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "Internal server error"}), 500
    return render_template("coming_soon.html", user=get_current_user(), title="Server Error", subtitle="An unexpected error occurred"), 500


@app.route("/subscription")
@login_required
def subscription_page():
    user = get_current_user()
    status = subscription_status_payload(user)
    payments = PaymentTransaction.query.filter_by(user_id=user.id).order_by(PaymentTransaction.id.desc()).limit(50).all()
    licenses = License.query.filter_by(user_id=user.id).order_by(License.id.desc()).limit(20).all()
    return render_template(
        "subscription.html",
        user=user,
        subscription=status,
        pricing=PLAN_PRICING,
        payments=payments,
        licenses=licenses,
    )


@app.route("/api/subscription/status")
@login_required
def subscription_status_api():
    return jsonify(subscription_status_payload(get_current_user()))


@app.route("/api/subscription/upgrade", methods=["POST"])
@login_required
def subscription_upgrade_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    plan = (payload.get("plan") or request.form.get("plan") or "").strip().upper()
    provider = (payload.get("provider") or request.form.get("provider") or "mpesa").strip().lower()
    prompt = (payload.get("prompt") or request.form.get("prompt") or "").strip()

    if plan not in PLAN_PRICING:
        return jsonify({"ok": False, "message": "Unknown subscription plan."}), 400

    user = get_current_user()
    amount = PLAN_PRICING[plan]
    metadata = {"user_id": user.id, "plan": plan}
    if prompt:
        metadata["prompt"] = prompt

    payment = payment_service.create_payment(
        provider=provider,
        amount=amount,
        currency="USD",
        metadata=metadata,
    )
    if not payment.get("ok"):
        return jsonify({"ok": False, "message": payment.get("error", "Payment failed")}), 400

    transaction = PaymentTransaction(
        user_id=user.id,
        provider=payment["provider"],
        reference=payment["reference"],
        plan_name=plan,
        amount=amount,
        currency=payment.get("currency", "USD"),
        status=payment.get("status", "PENDING"),
        metadata_json=json.dumps(payment.get("metadata") or {}),
    )
    db.session.add(transaction)
    db.session.commit()
    # If running in testing mode, keep previous behavior (immediate activation)
    if app.testing or payment.get("status", "PENDING") == "SUCCESS":
        subscription = create_or_update_subscription(user, plan)
        license_row, license_message = ensure_license_for_current_mt5(user, plan)
        # If license generation failed due to existing license on another user, surface the error.
        if not license_row and "already licensed" in (license_message or ""):
            log_audit("subscription_failed", target=plan, details=license_message)
            return jsonify({"ok": False, "message": license_message}), 409

        log_audit(
            "subscription_upgraded",
            target=plan,
            details=json.dumps({"provider": provider, "reference": transaction.reference, "license": license_message}),
        )
        return jsonify({
            "ok": True,
            "message": f"Subscription upgraded to {plan}.",
            "payment": {
                "provider": transaction.provider,
                "reference": transaction.reference,
                "status": transaction.status,
                "amount": transaction.amount,
            },
            "subscription": subscription_status_payload(user),
            "license": {
                "key": license_row.license_key if license_row else None,
                "status": license_row.status if license_row else "MISSING",
                "mt5_account": license_row.mt5_account if license_row else None,
            },
        })

    # Production/non-testing: payment pending integration — do not activate license yet.
    log_audit(
        "subscription_pending",
        target=plan,
        details=json.dumps({"provider": provider, "reference": transaction.reference}),
    )
    return jsonify({
        "ok": True,
        "message": "Payment is pending integration. Subscription will activate once payment is confirmed.",
        "payment": {
            "provider": transaction.provider,
            "reference": transaction.reference,
            "status": transaction.status,
            "amount": transaction.amount,
        },
    })


@app.route("/api/subscription/cancel", methods=["POST"])
@login_required
def subscription_cancel_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    user = get_current_user()
    subscription = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.id.desc()).first()
    if not subscription:
        return jsonify({"ok": False, "message": "No subscription found."}), 404

    subscription.status = "EXPIRED"
    subscription.auto_renew = False
    subscription.cancelled_at = _now_utc()
    db.session.commit()

    log_audit("subscription_cancelled", target=subscription.plan_name)
    return jsonify({"ok": True, "message": "Subscription cancelled.", "subscription": subscription_status_payload(user)})


@app.route("/api/subscription/renew", methods=["POST"])
@login_required
def subscription_renew_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    user = get_current_user()
    current = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.id.desc()).first()
    if not current:
        return jsonify({"ok": False, "message": "No subscription to renew."}), 404

    if current.status != "EXPIRED":
        return jsonify({"ok": False, "message": "Subscription cannot be renewed unless expired."}), 400

    renewed = create_or_update_subscription(user, current.plan_name)
    log_audit("subscription_renewed", target=user.id, details=current.plan_name)
    return jsonify({"ok": True, "message": "Subscription renewed.", "subscription": subscription_status_payload(user)})


@app.route("/api/payments/history")
@login_required
def payments_history_api():
    user = get_current_user()
    rows = PaymentTransaction.query.filter_by(user_id=user.id).order_by(PaymentTransaction.id.desc()).limit(100).all()
    return jsonify({
        "items": [
            {
                "provider": item.provider,
                "reference": item.reference,
                "plan": item.plan_name,
                "amount": item.amount,
                "currency": item.currency,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
            }
            for item in rows
        ]
    })


@app.route("/api/licenses/validate")
@login_required
def license_validate_api():
    user = get_current_user()
    mt5_account = (request.args.get("mt5_account") or "").strip() or (get_mt5_terminal_status().get("account_login") or user.mt5_account)
    if not mt5_account:
        return jsonify({"ok": False, "message": "MT5 account required"}), 400

    license_row = get_user_license(user, mt5_account)
    if not license_row:
        return jsonify({"ok": False, "message": "License not found"}), 404

    valid, message = validate_license_for_bot_start(user)
    return jsonify({
        "ok": valid,
        "message": message,
        "license": {
            "key": license_row.license_key,
            "status": license_row.status,
            "mt5_account": license_row.mt5_account,
            "expires_at": license_row.expires_at.isoformat() if license_row.expires_at else None,
        },
    })


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    metrics = admin_metrics_payload()
    recent_users = User.query.order_by(User.id.desc()).limit(20).all()
    licenses = License.query.order_by(License.id.desc()).limit(50).all()
    audits = AuditLog.query.order_by(AuditLog.id.desc()).limit(50).all()
    return render_template(
        "admin_dashboard.html",
        user=get_current_user(),
        metrics=metrics,
        recent_users=recent_users,
        licenses=licenses,
        audits=audits,
        is_admin_user=is_admin_user,
    )


@app.route("/api/admin/metrics")
@login_required
@admin_required
def admin_metrics_api():
    return jsonify(admin_metrics_payload())


@app.route("/api/admin/payments")
@login_required
@admin_required
def admin_payments_api():
    # Optional filter: provider, status, reference
    provider = (request.args.get('provider') or '').strip().lower()
    status = (request.args.get('status') or '').strip().upper()
    reference = (request.args.get('reference') or '').strip()
    query = PaymentTransaction.query
    if provider:
        query = query.filter(PaymentTransaction.provider == provider)
    if status:
        query = query.filter(PaymentTransaction.status == status)
    if reference:
        query = query.filter(PaymentTransaction.reference.ilike(f"%{reference}%"))
    rows = query.order_by(PaymentTransaction.id.desc()).limit(200).all()
    return jsonify({
        'items': [
            {
                'id': r.id,
                'user_id': r.user_id,
                'provider': r.provider,
                'reference': r.reference,
                'plan_name': r.plan_name,
                'amount': r.amount,
                'currency': r.currency,
                'status': r.status,
                'created_at': r.created_at.isoformat(),
            }
            for r in rows
        ]
    })


@app.route("/api/admin/licenses")
@login_required
@admin_required
def admin_list_licenses_api():
    # Optional query params: mt5_account, user_email
    mt5_q = (request.args.get("mt5_account") or "").strip()
    email_q = (request.args.get("email") or "").strip().lower()

    query = License.query
    if mt5_q:
        query = query.filter(License.mt5_account == mt5_q)
    if email_q:
        query = query.join(User, User.id == License.user_id).filter(User.email.ilike(f"%{email_q}%"))

    rows = query.order_by(License.id.desc()).limit(200).all()
    return jsonify({
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "license_key": row.license_key,
                "mt5_account": row.mt5_account,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "activated_at": row.activated_at.isoformat() if row.activated_at else None,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            }
            for row in rows
        ]
    })


@app.route("/api/admin/licenses/<int:license_id>/status", methods=["POST"])
@login_required
@admin_required
def admin_update_license_status_api(license_id):
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or request.form.get("status") or "").strip().upper()
    if status not in {"ACTIVE", "INACTIVE", "REVOKED"}:
        return jsonify({"ok": False, "message": "Invalid status."}), 400

    row = db.session.get(License, license_id)
    if not row:
        return jsonify({"ok": False, "message": "License not found."}), 404

    row.status = status
    if status == "ACTIVE":
        row.activated_at = _now_utc()
        row.revoked_at = None
    if status == "REVOKED":
        row.revoked_at = _now_utc()

    db.session.commit()
    log_audit("admin_license_status_update", target=row.license_key, details=f"status={status}")
    return jsonify({"ok": True, "message": "License updated."})


@app.route("/api/admin/users")
@login_required
@admin_required
def admin_users_api():
    # Optional query param: q (search username or email or mt5)
    q = (request.args.get("q") or "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter((User.username.ilike(like)) | (User.email.ilike(like)) | (User.mt5_account.ilike(like)))

    rows = query.order_by(User.id.desc()).limit(200).all()
    return jsonify({
        "items": [
            {
                "id": row.id,
                "username": row.username,
                "email": row.email,
                "mt5_account": row.mt5_account,
                "is_admin": is_admin_user(row),
            }
            for row in rows
        ]
    })


@app.route("/api/admin/users/<int:user_id>/admin", methods=["POST"])
@login_required
@admin_required
def admin_toggle_user_role_api(user_id):
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    make_admin = bool(payload.get("is_admin"))
    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify({"ok": False, "message": "User not found."}), 404

    existing = AdminRole.query.filter_by(user_id=user_id).first()

    if make_admin:
        if existing:
            existing.is_active = True
        else:
            db.session.add(AdminRole(user_id=user_id, is_active=True))
    else:
        if existing:
            existing.is_active = False

    db.session.commit()
    log_audit("admin_user_role_updated", target=str(user_id), details=f"is_admin={make_admin}")
    return jsonify({"ok": True, "message": "User role updated."})


@app.route("/api/admin/audit")
@login_required
@admin_required
def admin_audit_api():
    rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(200).all()
    return jsonify({
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "target": row.target,
                "ip_address": row.ip_address,
                "details": row.details,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    })


@app.route("/api/admin/backup", methods=["POST"])
@login_required
@admin_required
def admin_backup_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    db_path = app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    result = backup_service.create_backup(db_path)
    log_audit("admin_backup_created", details=json.dumps(result))
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/admin/restore", methods=["POST"])
@login_required
@admin_required
def admin_restore_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    backup_path = (payload.get("backup_path") or request.form.get("backup_path") or "").strip()
    if not backup_path:
        return jsonify({"ok": False, "message": "backup_path is required."}), 400

    db_path = app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    result = backup_service.restore_backup(backup_path, db_path)
    log_audit("admin_restore_executed", details=json.dumps(result))
    status = 200 if result.get("ok") else 400
    return jsonify(result), status

@app.route("/signals")
def signals():
    return jsonify(generate_signals())
    
@app.route("/bot_status")
def bot_status():
    mt5_status = get_mt5_terminal_status()
    bot_state = bot_manager.status()
    activity_log = bot_state.get("activity_log", [])

    return jsonify({
        "running": bot_state["running"],
        "status": bot_state["status"],
        "current_bot": bot_state["current_bot"],
        "start_time": bot_state["start_time"],
        "uptime": bot_state["uptime"],
        "last_execution": bot_state["last_execution"],
        "last_signal": bot_state["last_signal"],
        "last_trade_result": bot_state["last_trade_result"],
        "error": bot_state.get("error", ""),
        "mt5_connected": mt5_status["connected"],

        "logs": [event.get("message", "") for event in activity_log]

    })
    
    

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            token_record = PasswordResetToken.query.filter_by(user_id=user.id, used=False).order_by(PasswordResetToken.created_at.desc()).first()
            if token_record and token_record.expires_at > _now_utc():
                token = token_record.token
                code = token_record.code
            else:
                token = create_password_reset_token(user)
                token_record = PasswordResetToken.query.filter_by(token=token).first()
                code = token_record.code

            if not send_password_reset_email(user, code, token):
                flash("We could not send the reset email right now. Please try again later.", "error")
                return redirect(url_for("forgot_password"))

            session["password_reset_user_id"] = user.id
            log_audit("password_reset_requested", target=user.email)
            flash("If an account exists for that email, check your email for a reset code.", "success")
        else:
            session.pop("password_reset_user_id", None)
            log_audit("password_reset_requested_unknown", target=email)
            flash("If an account exists for that email, check your email for a reset code.", "success")

        return redirect(url_for("verify_reset_code"))

    return render_template("forgot_password.html")


@app.route("/verify-reset-code", methods=["GET", "POST"])
def verify_reset_code():
    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        code = request.form.get("code", "").strip()
        pending_user_id = session.get("password_reset_user_id")

        if not pending_user_id:
            flash("Please request a new reset code.", "error")
            return redirect(url_for("forgot_password"))

        token_record = (
            PasswordResetToken.query.filter_by(user_id=pending_user_id, code=code, used=False)
            .order_by(PasswordResetToken.created_at.desc())
            .first()
        )

        if not token_record or token_record.expires_at < _now_utc().replace(tzinfo=None):
            flash("The verification code is invalid or has expired.", "error")
            return render_template("verify_reset_code.html")

        return redirect(url_for("reset_password", token=token_record.token))

    return render_template("verify_reset_code.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset_token = PasswordResetToken.query.filter_by(token=token).first()

    if not reset_token or reset_token.used or reset_token.expires_at < _now_utc().replace(tzinfo=None):
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", token=token)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("reset_password.html", token=token)

        user = reset_token.user
        user.password = bcrypt.generate_password_hash(password).decode("utf-8")
        PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({PasswordResetToken.used: True})
        session.pop("password_reset_user_id", None)
        db.session.commit()

        log_audit("password_reset_completed", target=user.email)
        flash("Password changed successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        blocked, wait_seconds = login_rate_limited(email)
        if blocked:
            flash(f"Too many login attempts. Try again in {wait_seconds} seconds.", "error")
            log_audit("login_rate_limited", target=email, details=f"wait={wait_seconds}")
            return render_template("login.html")

        user = User.query.filter_by(email=email).first()

        if user and verify_password(user.password, password):
            if user.password == password:
                user.password = bcrypt.generate_password_hash(password).decode("utf-8")
                db.session.commit()
            login_user(user)
            session["user_id"] = str(user.id)
            session.permanent = True
            record_login_attempt(email, success=True)
            log_audit("login_success", target=email)
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        record_login_attempt(email, success=False)
        log_audit("login_failed", target=email)
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        email = request.form.get("email", "").strip().lower()
        if User.query.filter_by(email=email).first():
            log_audit("register_duplicate", target=email)
            flash("Email already exists. Please use another email address.", "error")
            return render_template("register.html")

        user = User(
            username=request.form.get("username", "").strip(),
            email=email,
            password=bcrypt.generate_password_hash(request.form.get("password", "")).decode("utf-8")
        )

        try:
            db.session.add(user)
            db.session.commit()
            log_audit("register_success", target=email, user_id=user.id)
        except IntegrityError:
            db.session.rollback()
            log_audit("register_integrity_error", target=email)
            flash("Email already exists. Please use another email address.", "error")
            return render_template("register.html")

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    log_audit("logout")
    logout_user()
    session.pop("user_id", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/mt5", methods=["GET", "POST"])
@login_required
def mt5_page():
    user = get_current_user()
    connection_error = None

    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        user.mt5_account = request.form.get("account", "").strip()
        user.mt5_server = request.form.get("server", "").strip()
        user.mt5_name = request.form.get("name", "").strip()
        user.mt5_connected = bool(user.mt5_account and user.mt5_server and user.mt5_name)
        db.session.commit()
        return redirect(url_for("mt5_page"))

    mt5_data = get_mt5_summary()
    positions = get_mt5_positions()
    history = get_mt5_history(limit=10)
    bot_state = bot_manager.status()
    is_connected = bool(mt5_data.get("connected"))

    if not is_connected:
        connection_error = "MT5 is not connected. Please ensure your terminal is signed in and the MT5 bridge is running."

    return render_template(
        "mt5.html",
        user=user,
        mt5=mt5_data,
        positions=positions,
        history=history,
        bot_state=bot_state,
        bot_status=bot_state.get("status", "Unknown"),
        bot_running=bot_state.get("running", False),
        bot_current_name=bot_state.get("current_bot", "Unknown"),
        is_connected=is_connected,
        connection_error=connection_error,
    )

@app.route("/test_mt5")
def test_mt5():
    if mt5 is None:
        return "❌ MetaTrader 5 is not installed."

    if not mt5.initialize():
        return "❌ Failed to connect to MetaTrader 5."

    account = mt5.account_info()

    if account is None:
        mt5.shutdown()
        return "❌ No MT5 account is logged in."

    data = f"""
    <h2>MT5 Connected</h2>
    <p><b>Account:</b> {account.login}</p>
    <p><b>Server:</b> {account.server}</p>
    <p><b>Balance:</b> {account.balance}</p>
    <p><b>Equity:</b> {account.equity}</p>
    <p><b>Profit:</b> {account.profit}</p>
    <p><b>Free Margin:</b> {account.margin_free}</p>
    """

    mt5.shutdown()

    return data


@app.route("/market_data")
def market_data():

    mt5_data = get_mt5_summary()
    market = get_market_data()
    signals = generate_signals()

    return jsonify({
        "status": mt5_data["status"],
        "connected": mt5_data["connected"],
        "balance": mt5_data["balance"],
        "equity": mt5_data["equity"],
        "profit": mt5_data["profit"],
        "margin": mt5_data["margin"],
        "markets": market,
        "signals": signals,
        "bot_running": bot_manager.status()["running"]
    })


@app.route("/dashboard")
@login_required
def dashboard():

    user = get_current_user()
    mt5_data = get_mt5_summary()
    market = get_market_data()
    signals = generate_signals()
    bot_state = bot_manager.status()

    return render_template(
        "dashboard.html",
        user=user,
        mt5=mt5_data,
        market=market,
        signals=signals,
        bot_running=bot_state["running"],
        bot_status=bot_state.get("status", "Unknown"),
        today_summary={
            "trades": 0,
            "win_rate": 0.0,
            "profit": 0.0,
        },
    )


@app.route("/bot-control")
@login_required
def bot_control():
    user = get_current_user()
    mt5_data = get_mt5_summary()
    refresh_mt5_bridge_state()
    bot_state = bot_manager.status()

    return render_template(
        "bot_control.html",
        user=user,
        mt5=mt5_data,
        bot_running=bot_state["running"],
        bot_status=bot_state.get("status", "Unknown"),
        bot_current=bot_state.get("current_bot", "Unknown"),
        bot_current_id=bot_state.get("current_bot_id", "hybrid_bot"),
        bot_uptime=bot_state.get("uptime", "00:00:00"),
        bot_last_signal=bot_state.get("last_signal", "N/A"),
        bot_last_trade_result=bot_state.get("last_trade_result", "N/A"),
        bots=bot_manager.available_bots(),
    )


@app.route("/analytics")
@login_required
def analytics():
    user = get_current_user()
    mt5_data = get_mt5_summary()
    market = get_market_data()
    bot_state = bot_manager.status()

    return render_template(
        "analytics.html",
        user=user,
        mt5=mt5_data,
        market=market,
        bot_running=bot_state["running"],
    )


@app.route("/markets")
@login_required
def markets():
    # Single market architecture - redirect to bot control
    return redirect(url_for("bot_control"))


@app.route("/ai-signals")
@login_required
def ai_signals():
    user = get_current_user()
    mt5_data = get_mt5_summary()
    bot_state = bot_manager.status()
    signals = generate_signals()
    market = get_market_data()

    return render_template(
        "ai_signals.html",
        user=user,
        mt5=mt5_data,
        bot_running=bot_state["running"],
        signals=signals,
        market=market,
    )


@app.route("/history")
@login_required
def trade_history():
    user = get_current_user()
    mt5_data = get_mt5_summary()
    bot_state = bot_manager.status()
    history_data = get_mt5_history(limit=50)

    return render_template(
        "history.html",
        user=user,
        mt5=mt5_data,
        bot_running=bot_state["running"],
        history=history_data,
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = get_current_user()
    mt5_data = get_mt5_summary()
    bot_state = bot_manager.status()

    if request.method == "POST":
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error

        username = request.form.get("username", user.username if user else "").strip()
        email = request.form.get("email", user.email if user else "").strip().lower()
        password = request.form.get("password", "")
        mt5_name = request.form.get("mt5_name", user.mt5_name if user else "").strip()
        mt5_account = request.form.get("mt5_account", user.mt5_account if user else "").strip()
        mt5_server = request.form.get("mt5_server", user.mt5_server if user else "").strip()

        if user:
            user.username = username or user.username
            user.email = email or user.email
            if password:
                user.password = bcrypt.generate_password_hash(password).decode("utf-8")
            user.mt5_name = mt5_name
            user.mt5_account = mt5_account
            user.mt5_server = mt5_server
            user.mt5_connected = bool(mt5_name and mt5_account and mt5_server)
            db.session.commit()
            flash("Settings updated successfully.", "success")
            return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        user=user,
        mt5=mt5_data,
        bot_running=bot_state["running"],
    )


@app.route("/start_bot")
@login_required
def start_bot():
    user = get_current_user()
    mt5_status = get_mt5_terminal_status()
    if mt5_status.get("connected"):
        ok, message = validate_license_for_bot_start(user)
        if not ok:
            flash(message, "error")
            log_audit("bot_start_blocked", details=message)
            return redirect(url_for("dashboard"))

    bot_manager.start(bot_id=bot_manager.status().get("current_bot_id"))
    log_audit("bot_start_requested", target=bot_manager.status().get("current_bot_id"))

    return redirect(url_for("bot_control"))


@app.route("/api/bot/start", methods=["POST"])
@login_required
def start_bot_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    app.logger.info("/api/bot/start called by user=%s", getattr(current_user, 'id', None))

    if not app.testing:
        ok, message = validate_license_for_bot_start(get_current_user())
        if not ok:
            log_audit("bot_start_blocked", target="gwarodollarprinter", details=message)
            return jsonify({"ok": False, "message": message, **bot_manager.status()})

    requested_bot = (payload.get("bot_id") or "gwarodollarprinter").strip()
    supported_bots = {bot.get("id") for bot in bot_manager.available_bots() if bot.get("id")}
    if requested_bot and requested_bot not in supported_bots and requested_bot not in {"gwarodollarprinter", "Gwaro Dollar Printer"}:
        return jsonify({"ok": False, "message": "Unsupported bot requested", **bot_manager.status()})

    ok, message = bot_manager.start(bot_id=requested_bot or "gwarodollarprinter")
    refresh_mt5_bridge_state()
    log_audit("bot_start_api", target="gwarodollarprinter", details=json.dumps({"ok": ok, "message": message}))
    
    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    
    # Record session and activity when a bot successfully starts
    try:
        if ok and current_user.is_authenticated:
            active_bot_id = "gwarodollarprinter"
            session_row = BotSession(
                user_id=current_user.id,
                bot_id=active_bot_id,
                mt5_account=current_user.mt5_account,
                status="RUNNING",
                started_at=_utc_now(),
            )
            db.session.add(session_row)
            db.session.commit()

            activity = BotActivityLog(
                session_id=session_row.id,
                user_id=current_user.id,
                type="Bot Started",
                message=message or "Bot started",
                details=json.dumps({"bot_id": active_bot_id, "symbol": "XAUUSD"}),
                created_at=_utc_now(),
            )
            db.session.add(activity)
            db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to record bot start session/activity")

    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "ok": ok,
        "success": ok,
        "message": message,
        "status": status_payload.get("status") or ("Running" if status_payload.get("running") else "Stopped"),
        "uptime": status_payload.get("uptime") or "0s",
        "last_signal": status_payload.get("last_signal") or "No signal yet",
        "mt5_connected": bool(mt5_summary.get("connected", False)),
        **status_payload,
    })

@app.route("/stop_bot")
@login_required
def stop_bot():
    bot_manager.stop(bot_id=bot_manager.status().get("current_bot_id"))

    return redirect(url_for("bot_control"))


@app.route("/api/bot/stop", methods=["POST"])
@login_required
def stop_bot_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    app.logger.info("/api/bot/stop called by user=%s", getattr(current_user, 'id', None))
    
    requested_bot = (payload.get("bot_id") or "gwarodollarprinter").strip() or "gwarodollarprinter"

    ok, message = bot_manager.stop(bot_id=requested_bot)
    log_audit("bot_stop_api", target="gwarodollarprinter", details=json.dumps({"ok": ok, "message": message}))
    
    # Record session stop and activity when a bot successfully stops
    try:
        if ok and current_user.is_authenticated:
            # find latest running session for this user
            running_session = BotSession.query.filter_by(user_id=current_user.id, status="RUNNING").order_by(BotSession.started_at.desc()).first()
            if running_session:
                running_session.status = "STOPPED"
                running_session.stopped_at = _utc_now()
                db.session.add(running_session)
                db.session.commit()

                activity = BotActivityLog(
                    session_id=running_session.id,
                    user_id=current_user.id,
                    type="Bot Stopped",
                    message=message or "Bot stopped",
                    details=json.dumps({"bot_id": running_session.bot_id, "symbol": "XAUUSD"}),
                    created_at=_utc_now(),
                )
                db.session.add(activity)
                db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to record bot stop session/activity")

    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "ok": ok,
        "success": ok,
        "message": message,
        "status": status_payload.get("status") or ("Running" if status_payload.get("running") else "Stopped"),
        "uptime": status_payload.get("uptime") or "0s",
        "last_signal": status_payload.get("last_signal") or "No signal yet",
        "mt5_connected": bool(mt5_summary.get("connected", False)),
        **status_payload,
    })


@app.route("/api/bot/activity")
@login_required
def bot_activity_api():
    limit = int(request.args.get("limit", 50))
    logs = BotActivityLog.query.filter_by(user_id=current_user.id).order_by(BotActivityLog.created_at.desc()).limit(limit).all()
    return jsonify({
        "ok": True,
        "activities": [
            {
                "id": l.id,
                "session_id": l.session_id,
                "type": l.type,
                "message": l.message,
                "details": l.details,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    })


@app.route("/api/bot/sessions")
@login_required
def bot_sessions_api():
    limit = int(request.args.get("limit", 50))
    sessions = BotSession.query.filter_by(user_id=current_user.id).order_by(BotSession.started_at.desc()).limit(limit).all()
    return jsonify({
        "ok": True,
        "sessions": [
            {
                "id": s.id,
                "bot_id": s.bot_id,
                "mt5_account": s.mt5_account,
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "stopped_at": s.stopped_at.isoformat() if s.stopped_at else None,
                "meta_json": s.meta_json,
            }
            for s in sessions
        ]
    })


@app.route("/api/bot/select", methods=["POST"])
@login_required
def select_bot_api():
    payload = request.get_json(silent=True) or {}
    requested_bot = (payload.get("bot_id") or "gwarodollarprinter").strip()
    ok, message = bot_manager.set_active_bot(requested_bot)
    return jsonify({"ok": ok, "message": message, **bot_manager.status()})


@app.route("/api/bot/status")
@login_required
def bot_status_api():
    refresh_mt5_bridge_state()
    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "bots": bot_manager.available_bots(),
        **status_payload,
        "mt5_bridge": bot_manager._bridge.get_status(),
        "mt5_status": mt5_summary.get("status", "Disconnected"),
        "mt5_connected": mt5_summary.get("connected", False),
        "balance": mt5_summary.get("balance", status_payload.get("balance")),
        "equity": mt5_summary.get("equity", status_payload.get("equity")),
        "profit": mt5_summary.get("profit", status_payload.get("profit")),
        "open_trades": status_payload.get("open_trades"),
    })


@app.route("/api/bot/refresh", methods=["POST"])
@login_required
def refresh_bot_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    refresh_mt5_bridge_state()
    ok, message = bot_manager.refresh_state()
    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "ok": ok,
        "success": ok,
        "message": message,
        "status": status_payload.get("status") or ("Running" if status_payload.get("running") else "Stopped"),
        "uptime": status_payload.get("uptime") or "0s",
        "last_signal": status_payload.get("last_signal") or "No signal yet",
        "mt5_connected": bool(mt5_summary.get("connected", False)),
        **status_payload,
    })


@app.route("/api/bot/close-all", methods=["POST"])
@login_required
def close_all_trades_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    requested_bot = (payload.get("bot_id") or "gwarodollarprinter").strip() or "gwarodollarprinter"
    ok, message = bot_manager.close_all_trades(bot_id=requested_bot)
    refresh_mt5_bridge_state()
    log_audit("bot_close_all_trades_api", target="gwarodollarprinter", details=json.dumps({"ok": ok, "message": message}))
    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "ok": ok,
        "success": ok,
        "message": message,
        "status": status_payload.get("status") or ("Running" if status_payload.get("running") else "Stopped"),
        "uptime": status_payload.get("uptime") or "0s",
        "last_signal": status_payload.get("last_signal") or "No signal yet",
        "mt5_connected": bool(mt5_summary.get("connected", False)),
        **status_payload,
    })


@app.route("/api/bot/breakeven", methods=["POST"])
@login_required
def break_even_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    requested_bot = (payload.get("bot_id") or "gwarodollarprinter").strip() or "gwarodollarprinter"
    ok, message = bot_manager.break_even(bot_id=requested_bot)
    refresh_mt5_bridge_state()
    log_audit("bot_break_even_api", target="gwarodollarprinter", details=json.dumps({"ok": ok, "message": message}))
    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "ok": ok,
        "success": ok,
        "message": message,
        "status": status_payload.get("status") or ("Running" if status_payload.get("running") else "Stopped"),
        "uptime": status_payload.get("uptime") or "0s",
        "last_signal": status_payload.get("last_signal") or "No signal yet",
        "mt5_connected": bool(mt5_summary.get("connected", False)),
        **status_payload,
    })


@app.route("/api/bot/restart", methods=["POST"])
@login_required
def restart_bot_api():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    payload = request.get_json(silent=True) or {}
    if not app.testing:
        ok, message = validate_license_for_bot_start(get_current_user())
        if not ok:
            log_audit("bot_restart_blocked", target="gwarodollarprinter", details=message)
            return jsonify({"ok": False, "message": message, **bot_manager.status()})

    requested_bot = (payload.get("bot_id") or "gwarodollarprinter").strip() or "gwarodollarprinter"
    mt5_status = get_mt5_terminal_status()
    ok, message = bot_manager.restart(
        bot_id=requested_bot,
        user=get_current_user(),
        mt5_account=mt5_status.get("account_login"),
        enforce_security=bool(mt5_status.get("connected")),
    )
    refresh_mt5_bridge_state()
    log_audit("bot_restart_api", target="gwarodollarprinter", details=json.dumps({"ok": ok, "message": message}))
    status_payload = bot_manager.status()
    mt5_summary = get_mt5_summary()
    return jsonify({
        "ok": ok,
        "success": ok,
        "message": message,
        "status": status_payload.get("status") or ("Running" if status_payload.get("running") else "Stopped"),
        "uptime": status_payload.get("uptime") or "0s",
        "last_signal": status_payload.get("last_signal") or "No signal yet",
        "mt5_connected": bool(mt5_summary.get("connected", False)),
        **status_payload,
    })


def initialize_database():
    """Initialize database tables safely, only creating missing tables."""
    with app.app_context():
        try:
            # Use SQLAlchemy inspector to check for existing tables
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            
            # Get all table names from the models
            all_model_tables = set(db.Model.metadata.tables.keys())
            
            # Calculate missing tables
            missing_tables = all_model_tables - existing_tables
            
            if missing_tables:
                # Only create the missing tables
                db.Model.metadata.create_all(db.engine, tables=[
                    db.Model.metadata.tables[table_name] 
                    for table_name in missing_tables
                ])
                app.logger.info(f"Created missing database tables: {missing_tables}")
            else:
                app.logger.info("All database tables already exist. Skipping creation.")
                
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
            # Fall back to create_all if inspector fails
            try:
                db.create_all()
                app.logger.info("Database tables created/verified via fallback method")
            except Exception as fallback_error:
                app.logger.critical(f"Failed to initialize database: {fallback_error}")
                raise

@app.route("/pricing")
def pricing_page():
    user = get_current_user()
    return render_template("pricing.html", user=user, pricing=PLAN_PRICING)


if __name__ == "__main__":
    # Initialize database only when running the app directly.
    initialize_database()
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=app_settings.debug,
    )
