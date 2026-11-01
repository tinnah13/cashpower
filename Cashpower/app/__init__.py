"""Cash Power Guard: builds the Flask app and connects the parts.

    auth.py      accounts, OTP, login, remember device
    meters.py    meters and the meter page
    members.py   inviting people to see a meter
    usage.py     purchases and readings
    forecast.py  the calculation (units bought, days left)
    views.py     landing page, dashboard, settings
"""
import secrets

from flask import Flask, abort, g, request, session

from config import Config

from .extensions import db


def create_app(overrides=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config.update(overrides or {})

    db.init_app(app)

    from . import auth, members, meters, models, usage, views  # noqa: F401  (models: so the tables are known)
    from .utils import LANGS, fmt_phone, csrf_token, tr

    for part in (views, auth, meters, usage, members):
        app.register_blueprint(part.bp)

    with app.app_context():
        db.create_all()

    @app.before_request
    def before():
        if request.method == "POST":
            if not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf", "x")):
                abort(400)
        q = request.args.get("lang")
        if q in LANGS:
            session["lang"] = q
        g.user = auth.load_user()
        g.lang = session.get("lang") or (g.user.lang if g.user else "en")
        if q in LANGS and g.user and g.user.lang != q:
            g.user.lang = q
            db.session.commit()

    @app.context_processor
    def inject():
        lang = g.get("lang", "en")
        return dict(t=lambda k: tr(k, lang), lang=lang, langs=LANGS, user=g.get("user"),
                    csrf=csrf_token, fmt_phone=fmt_phone, vat=app.config["VAT_PCT"],
                    otp_required=app.config["OTP_REQUIRED"])

    return app
