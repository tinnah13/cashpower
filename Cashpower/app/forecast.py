"""The calculation: how many kWh a payment buys, and when the units will run out."""
from datetime import date, timedelta

from flask import current_app
from sqlalchemy import func

from .extensions import db
from .models import Entry

# RWF per kWh for each monthly block, REG residential tariff Oct 2025, excluding VAT: first 20 kWh, next 30, the rest.
TARIFF = [(20, 89), (30, 310), (10 ** 9, 369)]


def kwh_from_rwf(rwf, used=0.0, vat_pct=None):
    """Units bought for `rwf`, given kWh already bought this month (it decides which price block we start in)."""
    if vat_pct is None:
        vat_pct = current_app.config["VAT_PCT"]
    left, kwh, floor = float(rwf), 0.0, 0.0
    for size, base_price in TARIFF:
        price = base_price * (1 + vat_pct / 100)
        ceil = floor + size
        if used >= ceil:
            floor = ceil
            continue
        room = ceil - max(used, floor)
        cost = room * price
        if left <= cost:
            return round(kwh + left / price, 2)
        kwh += room
        left -= cost
        floor = ceil
    return round(kwh, 2)


def bought_this_month_before(meter_id, day, entry_id=None):
    """kWh bought in the same month before this payment (same-day payments count only if entered earlier)."""
    month = day[:7] + "-01"
    q = db.session.query(func.coalesce(func.sum(Entry.kwh), 0)).filter(
        Entry.meter_id == meter_id, Entry.kind == "purchase", Entry.day >= month)
    if entry_id is None:
        q = q.filter(Entry.day <= day)
    else:
        q = q.filter((Entry.day < day) | ((Entry.day == day) & (Entry.id < entry_id)))
    return q.scalar()


def calibration(meter_id):
    """Learn from receipts: ratio of kWh really received to kWh the listed tariff predicts (VAT, fees, rounding).
    Returns (ratio, number_of_receipts_used)."""
    rows = (Entry.query.filter(Entry.meter_id == meter_id, Entry.kind == "purchase", Entry.estimated == 0,
                               Entry.rwf.isnot(None)).order_by(Entry.day, Entry.id).all())
    ratios = []
    for r in rows:
        model = kwh_from_rwf(r.rwf, bought_this_month_before(meter_id, r.day, r.id))
        if model > 0:
            ratios.append(r.kwh / model)
    if not ratios:
        return 1.0, 0
    ratios.sort()
    return round(min(max(ratios[len(ratios) // 2], 0.6), 1.05), 3), len(ratios)


def forecast(meter_id):
    """Estimate of units left now and the date range they run out. None when there is not enough data yet."""
    rows = Entry.query.filter_by(meter_id=meter_id).order_by(Entry.day, Entry.id).all()
    readings = [r for r in rows if r.kind == "reading"]
    purchases = [r for r in rows if r.kind == "purchase"]
    today = date.today()
    if not readings:
        return None
    rates = []
    for a, b in zip(readings, readings[1:]):
        days = (date.fromisoformat(b.day) - date.fromisoformat(a.day)).days
        if days < 1:
            continue
        bought = sum(p.kwh for p in purchases if a.day < p.day <= b.day or (p.day == a.day and p.id > a.id))
        used = a.kwh + bought - b.kwh
        if used > 0:
            rates.append(used / days)
    if not rates and len(purchases) >= 2:
        d = (date.fromisoformat(purchases[-1].day) - date.fromisoformat(purchases[0].day)).days
        if d >= 1:
            rates.append(sum(p.kwh for p in purchases[:-1]) / d)
    if not rates:
        return None
    rate = sum(rates[-3:]) / len(rates[-3:])
    last = readings[-1]
    added = sum(p.kwh for p in purchases if p.day > last.day or (p.day == last.day and p.id > last.id))
    elapsed = max((today - date.fromisoformat(last.day)).days, 0)
    bal = max(last.kwh + added - rate * elapsed, 0.0)
    days = bal / rate
    spread = min(0.15 + 0.03 * elapsed, 0.5)  # the older the last reading, the wider the range
    lo, hi = days * (1 - spread), days * (1 + spread)
    return dict(balance=round(bal, 1), rate=round(rate, 2), days=round(days, 1),
                lo=today + timedelta(days=int(lo)), hi=today + timedelta(days=int(round(hi))),
                buy_by=today + timedelta(days=max(int(lo) - 2, 0)), low=lo <= 3,
                age=elapsed, stale=elapsed >= 7, spread=round(spread * 100))
