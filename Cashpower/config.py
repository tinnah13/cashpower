"""All settings in one place. Every value can be overridden with an environment variable (CPG_...)."""
import os
import secrets

BASE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(BASE, "instance")


def _secret():
    """Use CPG_SECRET if given, otherwise keep one random key in instance/secret_key so logins survive a restart."""
    if os.environ.get("CPG_SECRET"):
        return os.environ["CPG_SECRET"]
    os.makedirs(INSTANCE, exist_ok=True)
    path = os.path.join(INSTANCE, "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


def _db_uri():
    if os.environ.get("CPG_DATABASE_URL"):  # e.g. mysql+pymysql://user:pass@localhost/cash_power_guard
        return os.environ["CPG_DATABASE_URL"]
    path = os.environ.get("CPG_DB") or os.path.join(INSTANCE, "cpg.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return "sqlite:///" + path


SMTP_HOST = os.environ.get("CPG_SMTP_HOST", "")


class Config:
    SECRET_KEY = _secret()
    SQLALCHEMY_DATABASE_URI = _db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # One-time codes (OTP)
    OTP_CHANNEL = os.environ.get("CPG_OTP_CHANNEL", "email")  # "email" or "sms"
    DEMO_OTP = os.environ.get("CPG_DEMO_OTP", "0" if SMTP_HOST else "1") == "1"  # show the code on screen
    # One-time code at sign-up and login. OFF by default for now ("0"). Turn on with CPG_OTP_REQUIRED=1.
    # Forgot-password always asks for a code, because it is the only proof the person owns the account.
    OTP_REQUIRED = os.environ.get("CPG_OTP_REQUIRED", "0") == "1"
    OTP_TTL_MIN = 5
    OTP_MAX_TRIES = 5
    OTP_RESEND_SEC = 60

    # Sign-in protection
    LOCK_AFTER = 5       # wrong passwords before the account is locked
    LOCK_MIN = 15        # minutes locked
    DEVICE_DAYS = 30     # "remember this device"
    DEVICE_COOKIE = "cpg_device"

    # Email (any SMTP server: Gmail app password, Brevo, Resend ...)
    SMTP_HOST = SMTP_HOST
    SMTP_PORT = int(os.environ.get("CPG_SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("CPG_SMTP_USER", "")
    SMTP_PASS = os.environ.get("CPG_SMTP_PASS", "")
    SMTP_FROM = os.environ.get("CPG_SMTP_FROM") or os.environ.get("CPG_SMTP_USER", "no-reply@localhost")

    # Listed REG prices exclude VAT. MyCashPower's calculator shows the listed price x 1.18, so 18% VAT is assumed.
    # NOT yet confirmed with a real receipt. Over-estimating units is the risky direction, so we keep the safer value.
    VAT_PCT = float(os.environ.get("CPG_VAT_PCT", "18"))
