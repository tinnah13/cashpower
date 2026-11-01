"""Usage records: a purchase (RWF paid, kWh received) or a meter reading (kWh left)."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, request, url_for

from .extensions import db
from .forecast import bought_this_month_before, calibration, kwh_from_rwf
from .models import Entry
from .utils import get_meter, iso, log_act, login_required, now, tr

bp = Blueprint("usage", __name__)


@bp.route("/meter/<int:mid>/entry", methods=["POST"])
@login_required
def add_entry(mid):
    m, role = get_meter(mid)
    if role not in ("owner", "add"):
        abort(403)
    kind = request.form.get("kind")
    try:
        day = date.fromisoformat(request.form.get("day", ""))
        if day > date.today():
            raise ValueError
    except ValueError:
        day = date.today()
    try:
        if kind == "purchase":
            rwf = int(request.form.get("rwf", "0"))
            if rwf <= 0:
                raise ValueError
            raw = request.form.get("kwh", "").strip()
            if raw:  # units copied from the receipt: exact
                kwh, est = float(raw), 0
            else:    # units worked out from the tariff, adjusted by what earlier receipts taught us
                used = bought_this_month_before(mid, day.isoformat())
                kwh, est = round(kwh_from_rwf(rwf, used) * calibration(mid)[0], 2), 1
        elif kind == "reading":
            rwf, est = None, 0
            kwh = float(request.form.get("balance", ""))
        else:
            abort(400)
        if kwh <= 0 and kind == "purchase" or kwh < 0:
            raise ValueError
    except ValueError:
        flash(tr("err_positive", g.lang), "err")
        return redirect(url_for("meters.meter_page", mid=mid))
    db.session.add(Entry(meter_id=mid, user_id=g.user.id, kind=kind, day=day.isoformat(), rwf=rwf, kwh=kwh,
                         estimated=est, created=iso(now())))
    log_act(mid, f"added_{kind}", f"{kwh} kWh" + (f", {rwf} RWF" if rwf else ""))
    db.session.commit()
    flash(tr("added_ok", g.lang), "ok")
    return redirect(url_for("meters.meter_page", mid=mid))
