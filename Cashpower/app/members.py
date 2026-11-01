"""People who can see a meter: the owner invites by phone number, the invited person accepts or declines."""
from flask import Blueprint, abort, flash, g, redirect, request, url_for
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Access
from .utils import (fmt_phone, get_meter, iso, log_act, login_required, normalize_phone, now, send_sms, tr)

bp = Blueprint("members", __name__)


@bp.route("/meter/<int:mid>/invite", methods=["POST"])
@login_required
def invite(mid):
    m, role = get_meter(mid)
    if role != "owner":
        abort(403)
    phone = normalize_phone(request.form.get("phone"))
    r = request.form.get("role", "view")
    if not phone:
        flash(tr("err_phone_invalid", g.lang), "err")
    elif phone == g.user.phone:
        flash(tr("err_self_invite", g.lang), "err")
    else:
        try:
            db.session.add(Access(meter_id=mid, phone=phone, role="add" if r == "add" else "view", status="pending",
                                  invited_by=g.user.id, created=iso(now())))
            log_act(mid, "invited", fmt_phone(phone))
            db.session.commit()
            send_sms(phone, f"{g.user.name} invited you to view a meter on Cash Power Guard. "
                            "Sign up or log in with this number to accept.")
            flash(tr("added_ok", g.lang), "ok")
        except IntegrityError:
            db.session.rollback()
            flash(tr("err_already_invited", g.lang), "err")
    return redirect(url_for("meters.meter_page", mid=mid))


@bp.route("/meter/<int:mid>/revoke/<int:aid>", methods=["POST"])
@login_required
def revoke(mid, aid):
    m, role = get_meter(mid)
    if role != "owner":
        abort(403)
    a = Access.query.filter_by(id=aid, meter_id=mid).first()
    if a:
        log_act(mid, "removed", fmt_phone(a.phone))
        db.session.delete(a)
        db.session.commit()
    return redirect(url_for("meters.meter_page", mid=mid))


@bp.route("/invite/<int:aid>/<choice>", methods=["POST"])
@login_required
def answer_invite(aid, choice):
    a = Access.query.filter_by(id=aid, phone=g.user.phone, status="pending").first()
    if not a:
        abort(404)
    if choice == "accept":
        a.status = "active"
        log_act(a.meter_id, "accepted", g.user.name)
    elif choice == "decline":
        log_act(a.meter_id, "declined", g.user.name)
        db.session.delete(a)
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("views.dashboard"))
