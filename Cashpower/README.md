# Cash Power Guard (web app)

Tells a household when their prepaid Cash Power units will run out. Built with Flask and SQLAlchemy.

## Run (Windows PowerShell, from this folder)

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python run.py          # http://127.0.0.1:5000

Mac/Linux/Git Bash: `./setup.sh` does the first three lines. The database file is created by itself in `instance/cpg.db`.
Run the app always from this same folder, otherwise you will see a different (empty) database.

## Where things are

    run.py            starts the app
    config.py         every setting in one place (OTP times, lockout, email, VAT, database)
    app/
      __init__.py     builds the app and connects the parts
      models.py       the tables (users, meters, access, entries, otps, devices, activity)
      auth.py         sign-up, login, OTP (code), forgot password, remember this device, logout
      meters.py       add a meter, the meter page
      members.py      the owner invites people to view or add
      usage.py        purchases and meter readings
      forecast.py     the calculation: kWh bought, days left, receipt calibration
      views.py        landing page, dashboard, settings, error pages
      utils.py        checks (phone, password), translations, email/SMS sending, who may do what
      extensions.py   the shared database object
      templates/ static/ translations/   pages, style and the en/fr/rw texts
    sql/              the same tables as MySQL files, 00 to 05 (04 and 05 are planned, not used yet)
    tests/            python tests/test_app.py (code ON) and python tests/test_no_otp.py (code OFF)
    check_email.py    tests the email settings
    check_login.py    finds why a login fails

## How it works
- The one-time 6-digit code is **switched off** at sign-up and login for now (account is created and login works with the password). Switch it on with `$env:CPG_OTP_REQUIRED="1"`; it is then sent by email, or shown on screen in demo mode. **Forgot password always asks for a code**, because it is the only proof the person owns the account.
- One account per phone number and one owner per meter number (enforced by the database).
- "Remember this device" keeps a 30-day login on that browser only. The password is never stored in the browser by the app.
- The owner invites people by phone number (view only, or can add purchases). They accept from their dashboard.
- Units are priced with the Oct 2025 REG tariff plus VAT (`CPG_VAT_PCT`, default 18, NOT yet confirmed with a receipt). Receipts logged with their kWh calibrate the estimate.
- Languages: English, French, Kinyarwanda (`app/translations/*.json`; French and Kinyarwanda need a native-speaker review).
- Set `CPG_SECRET` to a fixed random value in production and serve over HTTPS.

## Sending the code by email (only needed when the code is switched on; set once by the team, users do nothing)
Set these in the same terminal, then run `python run.py`. Without them the app stays in demo mode.

    $env:CPG_SMTP_HOST="smtp.gmail.com"
    $env:CPG_SMTP_PORT="587"
    $env:CPG_SMTP_USER="your.address@gmail.com"
    $env:CPG_SMTP_PASS="<Gmail app password, no spaces>"
    $env:CPG_SMTP_FROM="Cash Power Guard <your.address@gmail.com>"

Test them first: `python check_email.py someone@gmail.com`. To show the code on screen anyway: `$env:CPG_DEMO_OTP="1"`.
For a real launch use a sending service such as Brevo or Resend (same five settings, different values).
To use SMS instead set `CPG_OTP_CHANNEL=sms` and fill in `send_sms()` in `app/utils.py`.

## Using MySQL instead of SQLite
Run `sql/00_database.sql` to `05_ussd.sql` in order, `pip install PyMySQL`, then set
`$env:CPG_DATABASE_URL="mysql+pymysql://user:password@localhost/cash_power_guard"` before `python run.py`.
(The SQL files were written for MySQL 8 but not yet run against a MySQL server.)

## If a login fails
`python check_login.py 07XXXXXXXXX` shows whether the account exists in this folder's database, whether it is locked, and whether the password you type matches.
