"""Find out why a login fails. Run this in the project folder:

    python check_login.py            (lists the accounts in this folder's database)
    python check_login.py 0788123456 (also lets you type a password to test it)

Passwords are never shown or stored. It only reads instance/cpg.db.
"""
import getpass
import os
import re
import sqlite3
import sys

from werkzeug.security import check_password_hash

path = os.environ.get("CPG_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "cpg.db"))
print("Database file:", path)
if not os.path.exists(path):
    sys.exit("This file does not exist yet. No account has ever been created from this folder. "
             "(Are you running run.py from a different folder than before?)")
con = sqlite3.connect(path)
con.row_factory = sqlite3.Row
rows = con.execute("SELECT uid, name, phone, email, failed, locked_until FROM users ORDER BY id").fetchall()
print(f"{len(rows)} account(s):")
for r in rows:
    lock = f"  LOCKED until {r['locked_until']}" if r["locked_until"] else ""
    print(f"  {r['uid']}  {r['name']:<22} {r['phone']}  {r['email']}  failed tries: {r['failed']}{lock}")
if len(sys.argv) > 1:
    d = re.sub(r"\D", "", sys.argv[1])
    if d.startswith("250") and len(d) == 12:
        d = "0" + d[3:]
    elif len(d) == 9:
        d = "0" + d
    u = con.execute("SELECT * FROM users WHERE phone=?", (d,)).fetchone()
    if not u:
        sys.exit(f"\nNo account has the number {d}. If you signed up, you probably never entered the code, so the account was never created.")
    print(f"\nAccount found for {d}: {u['name']} ({u['uid']}).")
    pw = getpass.getpass("Type the password you use (it will not show): ")
    print("PASSWORD MATCHES." if check_password_hash(u["pw_hash"], pw) else
          "Password does NOT match. Use 'Forgot password' on the login page to set a new one, "
          "and check that your browser did not auto-fill an older password.")
