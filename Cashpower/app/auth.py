"""Accounts: sign-up, login, one-time codes (OTP), forgot password, remember this device, logout."""
import re
import secrets
from datetime import timedelta

from flask import (Blueprint, current_app, flash, g, jsonify, make_response, redirect, render_template, request,
                   session, url_for)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import Device, Meter, Otp, User
from .utils import (fmt_phone, iso, login_required, mask_email, normalize_phone, now, parse, password_ok, send_email,
                    send_sms, sha, tr, valid_meter)

bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------- one-time codes
def issue_otp(phone, purpose, email=None):
    """Create and send a code. Returns (code, was_emailed) or None if asked again too soon."""
    cfg = current_app.config
    last = Otp.query.filter_by(phone=phone, purpose=purpose).order_by(Otp.id.desc()).first()
    if last and (now() - parse(last.created)).total_seconds() < cfg["OTP_RESEND_SEC"]:
        return None
    code = f"{secrets.randbelow(10 ** 6):06d}"
    Otp.query.filter_by(phone=phone, purpose=purpose).update({"used": 1})
    db.session.add(Otp(phone=phone, purpose=purpose, code_hash=sha(f"{phone}:{purpose}:{code}"),
                       expires=iso(now() + timedelta(minutes=cfg["OTP_TTL_MIN"])), created=iso(now())))
    db.session.commit()
    text = (f"Your Cash Power Guard code is {code}. It is valid for {cfg['OTP_TTL_MIN']} minutes. "
            "If you did not ask for it, ignore this message.")
    if cfg["OTP_CHANNEL"] == "email" and email:
        sent = send_email(email, "Your Cash Power Guard code", text)
    else:
        send_sms(phone, text)
        sent = False
    return code, sent


def check_otp(phone, purpose, code):
    """Returns (ok, tries_left_or_None)."""
    cfg = current_app.config
    row = Otp.query.filter_by(phone=phone, purpose=purpose, used=0).order_by(Otp.id.desc()).first()
    if not row or parse(row.expires) < now() or row.tries >= cfg["OTP_MAX_TRIES"]:
        return False, None
    if secrets.compare_digest(row.code_hash, sha(f"{phone}:{purpose}:{code}")):
        row.used = 1
        db.session.commit()
        return True, None
    row.tries += 1
    db.session.commit()
    return False, cfg["OTP_MAX_TRIES"] - row.tries


def begin_otp(ctx):
    """Send a code for sign-up / login / reset and go to the code page."""
    cfg = current_app.config
    email = None
    if cfg["OTP_CHANNEL"] == "email":
        if ctx["purpose"] == "signup":
            email = (session.get("signup") or {}).get("email")
        else:
            u = User.query.filter_by(phone=ctx["phone"]).first()
            email = u.email if u else None
    ctx["channel"] = "email" if email else "sms"
    ctx["dest"] = mask_email(email) if email else fmt_phone(ctx["phone"])
    session["otp"] = ctx
    res = issue_otp(ctx["phone"], ctx["purpose"], email)
    if res is None:
        flash(tr("otp_wait", g.lang), "warn")
        return redirect(url_for("auth.otp"))
    code, sent = res
    ctx["sent"] = bool(sent)
    session["otp"] = ctx
    if cfg["DEMO_OTP"]:
        session["demo_code"] = code
    elif email and not sent:
        flash(tr("otp_mail_failed", g.lang), "err")
    return redirect(url_for("auth.otp"))


# ---------------------------------------------------------------- sessions and remembered devices
def start_session(user_id, remember=False):
    """Fresh session for the user. Returns the device token to put in a cookie when 'remember' is on."""
    cfg = current_app.config
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    session["uid"] = user_id
    if not remember:
        return None
    token = secrets.token_urlsafe(32)
    dev = Device(user_id=user_id, token_hash=sha(token), label=(request.headers.get("User-Agent") or "device")[:60],
                 expires=iso(now() + timedelta(days=cfg["DEVICE_DAYS"])), created=iso(now()))
    db.session.add(dev)
    db.session.commit()
    session["device"] = dev.id
    return token


def finish_login(user_id, remember, dest="views.dashboard"):
    token = start_session(user_id, remember)
    resp = make_response(redirect(url_for(dest)))
    if token:
        cfg = current_app.config
        resp.set_cookie(cfg["DEVICE_COOKIE"], token, max_age=cfg["DEVICE_DAYS"] * 86400, httponly=True, samesite="Lax")
    return resp


def load_user():
    """Runs before every request: finds who is signed in, including automatic login from a remembered device."""
    cfg = current_app.config
    uid = session.get("uid")
    if not uid:
        token = request.cookies.get(cfg["DEVICE_COOKIE"])
        if token:
            dev = Device.query.filter_by(token_hash=sha(token)).first()
            if dev and parse(dev.expires) > now():
                uid = dev.user_id
                session["uid"] = uid
                session["device"] = dev.id
    user = db.session.get(User, uid) if uid else None
    if uid and not user:
        session.pop("uid", None)
    return user


def create_account(s):
    """Create the user and the first meter from the sign-up data. Returns the user, or None if phone/meter got taken."""
    try:
        user = User(name=s["name"], phone=s["phone"], email=s["email"], acct_type=s["acct"],
                    pw_hash=s["pw_hash"], lang=g.lang, created=iso(now()))
        db.session.add(user)
        db.session.flush()  # gives the new row its number
        user.uid = f"CPG-{user.id:06d}"
        db.session.add(Meter(meter_no=s["meter"], nickname=s["nick"], owner_id=user.id, created=iso(now())))
        db.session.commit()
        return user
    except IntegrityError:
        db.session.rollback()
        return None


# ---------------------------------------------------------------- live checks used by the sign-up form
@bp.route("/api/check-phone")
def check_phone():
    p = normalize_phone(request.args.get("phone", ""))
    if not p:
        return jsonify(ok=False, msg=tr("err_phone_invalid", g.lang))
    if User.query.filter_by(phone=p).first():
        return jsonify(ok=False, msg=tr("err_phone_exists", g.lang), exists=True)
    return jsonify(ok=True)


@bp.route("/api/check-meter")
def check_meter():
    m = request.args.get("meter", "")
    if not valid_meter(m):
        return jsonify(ok=False, msg=tr("err_meter_invalid", g.lang))
    if Meter.query.filter_by(meter_no=m).first():
        return jsonify(ok=False, msg=tr("err_meter_exists", g.lang))
    return jsonify(ok=True)


# ---------------------------------------------------------------- sign-up
@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("views.dashboard"))
    if request.method == "POST":
        f = request.form
        name, email = f.get("name", "").strip(), f.get("email", "").strip()
        phone, meter = normalize_phone(f.get("phone")), re.sub(r"\s", "", f.get("meter_no", ""))
        nick = f.get("nickname", "").strip() or "Home"
        pw, acct = f.get("password", ""), f.get("acct_type", "household")
        err = None
        if len(name) < 3:
            err = "err_name"
        elif not phone:
            err = "err_phone_invalid"
        elif User.query.filter_by(phone=phone).first():
            err = "err_phone_exists"
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            err = "err_email"
        elif not valid_meter(meter):
            err = "err_meter_invalid"
        elif Meter.query.filter_by(meter_no=meter).first():
            err = "err_meter_exists"
        elif not password_ok(pw) or pw != f.get("confirm", ""):
            err = "err_password"
        elif not f.get("terms"):
            err = "err_terms"
        if err:
            flash(tr(err, g.lang), "err")
            return render_template("register.html", form=f), 400
        session["signup"] = dict(name=name, email=email, phone=phone, meter=meter, nick=nick[:30],
                                 acct=acct if acct in ("household", "business", "landlord") else "household",
                                 pw_hash=generate_password_hash(pw))
        if not current_app.config["OTP_REQUIRED"]:
            user = create_account(session["signup"])
            session.pop("signup", None)
            if not user:
                flash(tr("err_phone_exists", g.lang), "err")
                return redirect(url_for("auth.register"))
            return finish_login(user.id, False, "views.welcome")
        return begin_otp(dict(purpose="signup", phone=phone))
    return render_template("register.html", form={})


# ---------------------------------------------------------------- login
@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("views.dashboard"))
    if request.method == "POST":
        cfg = current_app.config
        phone = normalize_phone(request.form.get("phone"))
        pw = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        u = User.query.filter_by(phone=phone).first() if phone else None
        if u and u.locked_until and parse(u.locked_until) > now():
            flash(tr("err_locked", g.lang), "err")
            return render_template("login.html"), 429
        if not u or not check_password_hash(u.pw_hash, pw):
            if u:
                fails = (u.failed or 0) + 1
                lock = iso(now() + timedelta(minutes=cfg["LOCK_MIN"])) if fails >= cfg["LOCK_AFTER"] else None
                u.failed, u.locked_until = (0 if lock else fails), lock
                db.session.commit()
            if not phone:
                flash(tr("err_phone_invalid", g.lang), "err")
            elif not u:
                flash(tr("err_no_account", g.lang) + (" " + tr("err_no_account_hint", g.lang)
                                                      if cfg["OTP_REQUIRED"] else ""), "err")
            else:
                flash(tr("err_login", g.lang), "err")
            return render_template("login.html"), 401
        u.failed, u.locked_until = 0, None
        db.session.commit()
        if not cfg["OTP_REQUIRED"]:
            return finish_login(u.id, remember)
        return begin_otp(dict(purpose="login", phone=phone, remember=remember))
    return render_template("login.html")


@bp.route("/otp", methods=["GET", "POST"])
def otp():
    ctx = session.get("otp")
    if not ctx:
        flash(tr("err_session", g.lang), "err")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        code = re.sub(r"\D", "", request.form.get("code", ""))
        ok, left = check_otp(ctx["phone"], ctx["purpose"], code)
        if not ok:
            msg = f'{tr("otp_wrong", g.lang)} {left}' if left is not None else tr("otp_expired", g.lang)
            flash(msg, "err")
            return render_template("otp.html", ctx=ctx, demo=session.get("demo_code")), 400
        session.pop("otp", None)
        session.pop("demo_code", None)
        if ctx["purpose"] == "signup":
            s = session.get("signup")
            if not s or s["phone"] != ctx["phone"]:
                flash(tr("err_session", g.lang), "err")
                return redirect(url_for("auth.register"))
            user = create_account(s)
            if not user:  # phone or meter taken between steps
                flash(tr("err_phone_exists", g.lang), "err")
                return redirect(url_for("auth.register"))
            return finish_login(user.id, False, "views.welcome")
        if ctx["purpose"] == "login":
            u = User.query.filter_by(phone=ctx["phone"]).first()
            return finish_login(u.id, ctx.get("remember", False))
        if ctx["purpose"] == "reset":
            session["reset_ok"] = ctx["phone"]
            return redirect(url_for("auth.reset_new"))
    return render_template("otp.html", ctx=ctx, demo=session.get("demo_code"))


@bp.route("/otp/resend", methods=["POST"])
def otp_resend():
    ctx = session.get("otp")
    if not ctx:
        return redirect(url_for("auth.login"))
    return begin_otp(ctx)


# ---------------------------------------------------------------- forgot password
@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        phone = normalize_phone(request.form.get("phone"))
        if not phone:
            flash(tr("err_phone_invalid", g.lang), "err")
        elif not User.query.filter_by(phone=phone).first():
            flash(tr("err_no_account", g.lang), "err")
        else:
            return begin_otp(dict(purpose="reset", phone=phone))
    return render_template("forgot.html")


@bp.route("/reset", methods=["GET", "POST"])
def reset_new():
    phone = session.get("reset_ok")
    if not phone:
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        if not password_ok(pw) or pw != request.form.get("confirm", ""):
            flash(tr("err_password", g.lang), "err")
        else:
            u = User.query.filter_by(phone=phone).first()
            u.pw_hash, u.failed, u.locked_until = generate_password_hash(pw), 0, None
            Device.query.filter_by(user_id=u.id).delete()  # every remembered device must sign in again
            db.session.commit()
            session.pop("reset_ok", None)
            flash(tr("pw_changed", g.lang), "ok")
            return redirect(url_for("auth.login"))
    return render_template("reset.html")


# ---------------------------------------------------------------- logout
@bp.route("/logout", methods=["POST"])
def logout():
    dev = session.get("device")
    if dev:
        Device.query.filter_by(id=dev).delete()
        db.session.commit()
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    resp = make_response(redirect(url_for("auth.login")))
    resp.delete_cookie(current_app.config["DEVICE_COOKIE"])
    return resp


@bp.route("/settings/logout-all", methods=["POST"])
@login_required
def logout_all():
    Device.query.filter_by(user_id=g.user.id).delete()
    db.session.commit()
    return logout()
