"""Tests with the one-time code switched OFF (the default): python tests/test_no_otp.py"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['CPG_DB'] = os.path.join(tempfile.mkdtemp(), 'n.db')
os.environ.pop('CPG_SMTP_HOST', None)
from app import create_app
APP = create_app({'OTP_RESEND_SEC': 0})
assert APP.config['OTP_REQUIRED'] is False
ok = lambda n, c: print(('PASS ' if c else 'FAIL ') + n) or (c or sys.exit(1))

def mk():
    c = APP.test_client(); c.get('/login'); return c
def post(c, url, **d):
    with c.session_transaction() as s: d['csrf'] = s['csrf']
    return c.post(url, data=d)
reg = dict(name='Alice Uwase', phone='0788123456', email='a@b.rw', meter_no='01234567890', nickname='Home',
           password='Str0ng!pass', confirm='Str0ng!pass', terms='1', acct_type='household')

a = mk()
r = post(a, '/register', **reg)
ok('sign-up creates the account straight away (no code page)', r.status_code == 302 and r.location.endswith('/welcome'))
ok('welcome shows DB ID', b'CPG-000001' in a.get('/welcome').data)
ok('register button says Create account, not Send code', b'Send code' not in mk().get('/register').data)
b = mk()
ok('duplicate phone still rejected', post(b, '/register', **{**reg, 'meter_no': '09999999999'}).status_code == 400)
ok('duplicate meter still rejected', post(b, '/register', **{**reg, 'phone': '0788999999'}).status_code == 400)
c = mk()
ok('wrong password rejected', post(c, '/login', phone='0788123456', password='Wrong!pass1').status_code == 401)
r = post(c, '/login', phone='0788123456', password='Str0ng!pass')
ok('right password logs in directly', r.status_code == 302 and r.location.endswith('/dashboard'))
ok('dashboard opens', c.get('/dashboard').status_code == 200)
d = mk()
r = post(d, '/login', phone='0788123456', password='Str0ng!pass', remember='1')
ok('remember device sets cookie', 'cpg_device' in r.headers.get('Set-Cookie', ''))
ok('remembered device logs in automatically', d.get('/dashboard').status_code == 200)
e = mk()
r = post(e, '/forgot', phone='0788123456')
ok('forgot password still asks for a code', r.location.endswith('/otp'))
ok('no-account message has no "finish sign-up" hint', b'only created after you enter the code' not in post(mk(), '/login', phone='0788000111', password='x').data)
print('ALL PASSED')
