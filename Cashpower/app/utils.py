"""Small helpers used by many files: time, phone/password checks, translations, email/SMS, access rules."""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps
from types import SimpleNamespace

from flask import abort, current_app, g, redirect, session, url_for

from .extensions import db
from .models import Access, Activity, Meter

# ---------------------------------------------------------------- translations
LANGS = {"en": "English", "fr": "Français", "rw": "Kinyarwanda"}
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
_TEXT = {}
for _code in LANGS:
    with open(os.path.join(_DIR, f"{_code}.json"), encoding="utf-8") as _f:
        _TEXT[_code] = json.load(_f)


def tr(key, lang="en"):
    """Text for `key` in `lang`; falls back to English, then to the key itself."""
    return _TEXT.get(lang, {}).get(key) or _TEXT["en"].get(key, key)


# ---------------------------------------------------------------- time
def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def parse(s):
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------- checks and formats
def normalize_phone(raw):
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("250") and len(d) == 12:
        d = "0" + d[3:]
    elif len(d) == 9:
        d = "0" + d
    return d if re.fullmatch(r"07[2389]\d{7}", d) else None


def fmt_phone(p):
    return f"{p[:4]} {p[4:7]} {p[7:]}"


def password_ok(pw):
    common = {"password", "12345678", "123456789", "qwertyui", "password1", "iloveyou"}
    return bool(len(pw) >= 8 and re.search(r"[A-Z]", pw) and re.search(r"[a-z]", pw)
                and re.search(r"\d", pw) and re.search(r"[^\w\s]|_", pw) and pw.lower() not in common)


def valid_meter(m):
    return bool(re.fullmatch(r"\d{11}", m or ""))


def mask_email(e):
    name, _, dom = e.partition("@")
    return (name[:1] + "***@" + dom) if dom else e


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def row_ns(obj, **extra):
    """Copy a model row into a plain object and add extra fields (for joined lists shown in templates)."""
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    data.update(extra)
    return SimpleNamespace(**data)


# ---------------------------------------------------------------- sending messages
def send_sms(phone, text):
    """Plug a licensed SMS provider in here (e.g. Africa's Talking). Until then it only writes to the log."""
    current_app.logger.info("SMS to %s: %s", phone, text)


def send_email(to, subject, body):
    """Send through the SMTP server set in config.py. Returns True if the server accepted the message."""
    cfg = current_app.config
    if not cfg["SMTP_HOST"]:
        current_app.logger.info("Email to %s (no SMTP configured): %s | %s", to, subject, body)
        return False
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["SMTP_FROM"], to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as s:
            s.starttls()
            if cfg["SMTP_USER"]:
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
            s.send_message(msg)
        return True
    except Exception as e:  # network, login, bad address ...
        current_app.logger.error("Email to %s failed: %s", to, e)
        return False


# ---------------------------------------------------------------- who may do what
def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not g.user:
            return redirect(url_for("auth.login"))
        return f(*a, **k)
    return wrapper


def role_for(meter, user):
    """'owner', 'add', 'view' or None."""
    if meter.owner_id == user.id:
        return "owner"
    a = Access.query.filter_by(meter_id=meter.id, phone=user.phone, status="active").first()
    return a.role if a else None


def get_meter(mid):
    m = db.session.get(Meter, mid)
    if not m:
        abort(404)
    r = role_for(m, g.user)
    if not r:
        abort(403)
    return m, r


def log_act(meter_id, action, detail=""):
    db.session.add(Activity(meter_id=meter_id, user_id=g.user.id if g.user else None,
                            action=action, detail=detail, ts=iso(now())))
