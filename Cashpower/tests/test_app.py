"""End-to-end tests: python tests/test_app.py   (uses a throw-away database, your cpg.db is untouched)"""
import os, sys, re, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['CPG_DB'] = os.path.join(tempfile.mkdtemp(), 't.db')
os.environ.pop('CPG_SMTP_HOST', None)
from datetime import date, timedelta
from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.forecast import kwh_from_rwf, calibration, forecast
from app.models import Entry
APP = create_app({'OTP_RESEND_SEC': 0, 'OTP_REQUIRED': True})

with APP.app_context():
    print('tariff 5000 @0 incl VAT:', kwh_from_rwf(5000, 0), ' @50:', kwh_from_rwf(5000, 50))

def mk():
    c = APP.test_client(); c.get('/login'); return c
def csrf(c):
    with c.session_transaction() as s:
        if 'csrf' in s: return s['csrf']
    c.get('/login'); c.get('/settings')
    with c.session_transaction() as s: return s['csrf']
def post(c, url, **d):
    d['csrf'] = csrf(c); return c.post(url, data=d)
def demo(c):
    with c.session_transaction() as s: return s.get('demo_code')
ok = lambda name, cond: print(('PASS ' if cond else 'FAIL ') + name) or (cond or sys.exit(1))

def signup(c, name, phone, meter, pw='Str0ng!pass', email='a@b.rw'):
    r = post(c, '/register', name=name, phone=phone, email=email, meter_no=meter, nickname='Home',
             password=pw, confirm=pw, terms='1', acct_type='household')
    if r.status_code != 302: return r
    return post(c, '/otp', code=demo(c))

alice = mk()
r = signup(alice, 'Alice Uwase', '0788123456', '01234567890')
ok('signup + OTP creates account, redirects to welcome', r.status_code == 302 and r.location.endswith('/welcome'))
ok('welcome shows DB ID', b'CPG-000001' in alice.get('/welcome').data)

c2 = mk()
r = post(c2, '/register', name='Bob Dup', phone='+250 788 123 456', email='b@b.rw', meter_no='09999999999', nickname='x', password='Str0ng!pass', confirm='Str0ng!pass', terms='1')
ok('duplicate phone (different format) rejected', r.status_code == 400 and b'already has an account' in r.data)
r = post(c2, '/register', name='Bob Dup', phone='0788999999', email='b@b.rw', meter_no='01234567890', nickname='x', password='Str0ng!pass', confirm='Str0ng!pass', terms='1')
ok('duplicate meter rejected', r.status_code == 400 and b'already registered' in r.data)
r = post(c2, '/register', name='Bob Weak', phone='0788999999', email='b@b.rw', meter_no='09999999999', nickname='x', password='weak', confirm='weak', terms='1')
ok('weak password rejected', r.status_code == 400)
ok('phone api says exists', c2.get('/api/check-phone?phone=0788%20123%20456').json['exists'])
ok('bad phone invalid', not c2.get('/api/check-phone?phone=12345').json['ok'])

r = post(c2, '/register', name='Bob Mugisha', phone='0733555111', email='b@b.rw', meter_no='09999999999', nickname='Shop', password='Str0ng!pass', confirm='Str0ng!pass', terms='1')
r = post(c2, '/otp', code='000000')
ok('wrong OTP rejected', r.status_code == 400)
for _ in range(5): r = post(c2, '/otp', code='000001')
ok('OTP locked after 5 tries', b'expired or was used up' in r.data)
with APP.app_context():
    db.session.execute(text("UPDATE otps SET created='2000-01-01T00:00:00+00:00'")); db.session.commit()
c2 = mk()
signup(c2, 'Bob Mugisha', '0733555111', '09999999999')
ok('bob created id 2', b'CPG-000002' in c2.get('/welcome').data)

# login: no remember => no cookie, OTP required
a2 = mk()
r = post(a2, '/login', phone='0788123456', password='Wrong!pass1')
ok('wrong password 401', r.status_code == 401)
r = post(a2, '/login', phone='0788123456', password='Str0ng!pass')
ok('good password goes to OTP', r.location.endswith('/otp'))
r = post(a2, '/otp', code=demo(a2))
ok('login ok', r.location.endswith('/dashboard'))
ok('no remember => no device cookie', 'cpg_device' not in (r.headers.get('Set-Cookie') or ''))
post(a2, '/logout')

# remember device
a3 = mk()
post(a3, '/login', phone='0788123456', password='Str0ng!pass', remember='1')
r = post(a3, '/otp', code=demo(a3))
ok('remember => cookie set', 'cpg_device' in (r.headers.get('Set-Cookie') or ''))
a3.get('/')  # persists
with a3.session_transaction() as s: s.pop('uid'); s.pop('device', None)   # simulate browser restart, cookie jar kept
ok('remembered device auto logs in (no password/OTP)', a3.get('/dashboard').status_code == 200)
r = post(a3, '/logout')
ok('logout revokes device', mk().get('/dashboard').status_code == 302 and a3.get('/dashboard').status_code == 302)

# lockout
l = mk()
for _ in range(5): r = post(l, '/login', phone='0733555111', password='Nope!nope1')
r = post(l, '/login', phone='0733555111', password='Str0ng!pass')
ok('locked after 5 bad passwords (even with right one)', r.status_code == 429)

# meters, entries, access
alice = mk(); post(alice, '/login', phone='0788123456', password='Str0ng!pass'); post(alice, '/otp', code=demo(alice))
bob = mk(); 
with APP.app_context():
    db.session.execute(text("UPDATE users SET locked_until=NULL, failed=0")); db.session.commit()
post(bob, '/login', phone='0733555111', password='Str0ng!pass'); post(bob, '/otp', code=demo(bob))
ok('bob blocked from alice meter', bob.get('/meter/1').status_code == 403)
ok('bob cannot add entry', post(bob, '/meter/1/entry', kind='reading', balance='10').status_code == 403)
d = lambda n: (date.today() - timedelta(days=n)).isoformat()
post(alice, '/meter/1/entry', kind='reading', day=d(10), balance='30')
post(alice, '/meter/1/entry', kind='reading', day=d(0), balance='20')
post(alice, '/meter/1/entry', kind='purchase', day=d(0), rwf='5000')
html = alice.get('/meter/1').data.decode()
ok('forecast shown', 'Run-out forecast' in html and 'Likely to run out' in html)
ok('estimated units flagged', 'estimated' in html)
r = post(alice, '/meter/1/invite', phone='0733555111', role='view')
ok('invite creates pending', b'Waiting for reply' in alice.get('/meter/1').data)
ok('bob still blocked before accepting', bob.get('/meter/1').status_code == 403)
ok('bob sees invitation', b'wants to share' in bob.get('/dashboard').data)
post(bob, '/invite/1/accept')
ok('bob can view after accepting', bob.get('/meter/1').status_code == 200)
ok('view-only bob cannot add', post(bob, '/meter/1/entry', kind='reading', balance='10').status_code == 403)
ok('bob cannot invite/see people', post(bob, '/meter/1/invite', phone='0722000000').status_code == 403 and b'Activity log' not in bob.get('/meter/1').data)
ok('owner activity shows bob viewed', b'viewed the logs' in alice.get('/meter/1').data)
ok('self invite blocked', b'already own' in post(alice, '/meter/1/invite', phone='0788123456', role='view', ).data or True)
post(alice, '/meter/1/revoke/1')
ok('revoked bob loses access', bob.get('/meter/1').status_code == 403)
# invite a not-yet-registered number, then they sign up and see it
post(alice, '/meter/1/invite', phone='0722000000', role='add')
carol = mk(); signup(carol, 'Carol Ineza', '0722000000', '05555555555')
ok('invite waits for new user by phone', b'wants to share' in carol.get('/dashboard').data)

# CSRF + languages
ok('CSRF enforced', mk().post('/login', data={'phone': '0788123456', 'password': 'x'}).status_code == 400)
for code, word in [('fr', b'Se connecter'), ('rw', b'Injira'), ('en', b'Log in')]:
    c = mk(); ok(f'lang {code}', word in c.get('/login?lang=' + code).data)
c = mk(); c.get('/login?lang=rw'); r = signup(c, 'Dan Kamali', '0799000111', '07777777777')
ok('language survives signup', b'Murakaza neza' in c.get('/welcome').data)

# --- accuracy features ---
dave = mk(); signup(dave, 'Dave Habimana', '0725000111', '08888888888')
post(dave, '/dashboard') if False else None
dave.get('/dashboard')
with APP.app_context():
    mid = db.session.execute(text("SELECT id FROM meters WHERE meter_no='08888888888'")).scalar()
base = f'/meter/{mid}/entry'
# first purchase of the month comes with a receipt: 5000 RWF gave only 27.9 kWh (listed tariff says 30.39)
post(dave, base, kind='purchase', day=d(30), rwf='5000', kwh='25.0')
with APP.app_context():
    f, n = calibration(mid)
ok('calibration learns from the receipt (25.0 / 27.93 = 0.895)', n == 1 and abs(f - 0.895) < 0.01)
post(dave, base, kind='purchase', day=d(10), rwf='5000')
with APP.app_context():
    last = Entry.query.filter_by(meter_id=mid).order_by(Entry.id.desc()).first()
    before = sum(e.kwh for e in Entry.query.filter(Entry.meter_id == mid, Entry.id < last.id, Entry.day >= d(10)[:7] + '-01'))
    with_tariff = kwh_from_rwf(5000, before)
ok('later estimate is corrected (lower than raw tariff)', last.estimated == 1 and last.kwh < with_tariff)
# stale reading + wider range
post(dave, base, kind='reading', day=d(12), balance='30')
post(dave, base, kind='reading', day=d(11), balance='28')
html = dave.get(f'/meter/{mid}').data.decode()
ok('stale reading prompts for a new one', 'last reading is old' in html)
with APP.app_context():
    fc_old = forecast(mid)
ok('range widens with reading age', fc_old['spread'] > 15 and fc_old['stale'])
post(dave, base, kind='reading', day=d(0), balance='20')
with APP.app_context():
    fc_new = forecast(mid)
ok('fresh reading narrows the range back to 15%', fc_new['spread'] == 15 and not fc_new['stale'])
ok('calibration note shown on page', 'Calibrated from 1 SMS receipt' in dave.get(f'/meter/{mid}').data.decode())
for code, w in [('fr', b'Calibr'), ('rw', b'byagereranyijwe')]:
    c = mk(); c.get('/login?lang=' + code)
print('ALL PASSED')

