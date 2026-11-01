"""Check that your email settings work, before trying the app.

    python check_email.py someone@gmail.com

Uses the same CPG_SMTP_* settings as the app. It sends one test email and tells you what went wrong, if anything.
"""
import os
import smtplib
import sys
from email.message import EmailMessage

to = sys.argv[1] if len(sys.argv) > 1 else ""
host = os.environ.get("CPG_SMTP_HOST", "")
port = int(os.environ.get("CPG_SMTP_PORT", "587"))
user = os.environ.get("CPG_SMTP_USER", "")
pw = os.environ.get("CPG_SMTP_PASS", "")
frm = os.environ.get("CPG_SMTP_FROM") or user

if not to:
    sys.exit("Usage: python check_email.py someone@gmail.com   (the address that should receive the test)")
missing = [n for n, v in [("CPG_SMTP_HOST", host), ("CPG_SMTP_USER", user), ("CPG_SMTP_PASS", pw)] if not v]
if missing:
    sys.exit("Not set yet: " + ", ".join(missing) + ".\nSet them in this same terminal first (see README, 'Sending the one-time code by email').")

msg = EmailMessage()
msg["From"], msg["To"], msg["Subject"] = frm, to, "Cash Power Guard test email"
msg.set_content("If you can read this, Cash Power Guard can send one-time codes by email.")
try:
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    print(f"Sent to {to}. Check the inbox and the spam folder.")
except smtplib.SMTPAuthenticationError:
    print("Login refused. For Gmail you need a 16-character APP PASSWORD (not your normal password), "
          "and 2-step verification must be on. Re-copy it without spaces.")
except (smtplib.SMTPConnectError, ConnectionError, TimeoutError, OSError) as e:
    print(f"Could not reach {host}:{port} ({e}). Check your internet, and that port {port} is not blocked by the network.")
except smtplib.SMTPRecipientsRefused:
    print("The receiving address was refused. Check that it is typed correctly.")
except Exception as e:
    print("Failed:", type(e).__name__, e)
