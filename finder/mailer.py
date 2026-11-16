"""Gmail sending for the LeadTube dashboard (optional; campaigns go through Smartlead).

Called by the dashboard with a JSON request on stdin; prints a JSON reply.

  python finder/mailer.py send  {"to", "subject", "body", "link"}  -> {"ok": true}
  python finder/mailer.py test  {}                                -> checks the login (sends nothing)

Your name, address and limits are in data/settings.json; the app password is
GMAIL_APP_PASSWORD in .env. Emails are sent exactly as written. Addresses on the
opt-out list (data/unsubscribed.json) and anything past the daily limit are refused.
"""

import json
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from settings import DATA_DIR, env

SETTINGS_FILE = DATA_DIR / "settings.json"     # from_name, from_email, smtp_host, smtp_port, daily_limit
SEND_LOG = DATA_DIR / "email_log.json"         # every email sent (date, to, subject, channel)
OPT_OUT = DATA_DIR / "unsubscribed.json"       # addresses that must never be emailed

DEFAULTS = {"from_name": "", "from_email": "", "smtp_host": "smtp.gmail.com", "smtp_port": 465, "daily_limit": 30}


class MailerError(Exception):
    pass


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return default


def write_json(path, value):
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1))
    tmp.replace(path)


def load_settings():
    return {**DEFAULTS, **read_json(SETTINGS_FILE, {}), "app_password": env("GMAIL_APP_PASSWORD")}


def sent_today(log):
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for e in log if e.get("date", "").startswith(today))


def smtp_connect(s):
    if not (s["from_email"] and s["app_password"]):
        raise MailerError("Add your email address and app password in Settings → Gmail first.")
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    port = int(s["smtp_port"] or 465)
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(s["smtp_host"], port, context=ctx, timeout=30)
        else:
            server = smtplib.SMTP(s["smtp_host"], port, timeout=30)
            server.starttls(context=ctx)
        server.login(s["from_email"], s["app_password"].replace(" ", ""))
        return server
    except smtplib.SMTPAuthenticationError:
        raise MailerError("Email login failed. For Gmail, use an App Password (not your normal "
                          "password): Google Account > Security > 2-Step Verification > App passwords.")
    except (OSError, smtplib.SMTPException) as e:
        raise MailerError(f"Couldn't connect to the email server: {e}")


def send(req):
    s = load_settings()
    to = (req.get("to") or "").strip()
    subject, body = (req.get("subject") or "").strip(), (req.get("body") or "").strip()
    if "@" not in to or any(c in to for c in " ,;<>\r\n"):
        raise MailerError("That email address doesn't look right.")
    if not subject or not body:
        raise MailerError("Subject and message can't be empty.")
    if to.lower() in {e.lower() for e in read_json(OPT_OUT, [])}:
        raise MailerError(f"{to} asked not to be emailed (on your opt-out list).")
    log = read_json(SEND_LOG, [])
    limit = int(s["daily_limit"] or 30)
    if sent_today(log) >= limit:
        raise MailerError(f"Daily limit reached ({limit} emails). Sending more from one inbox "
                          "risks the spam folder. It resets tomorrow; you can change it in Settings → Gmail.")

    msg = EmailMessage()
    msg["From"] = formataddr((s["from_name"], s["from_email"]))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=s["from_email"].split("@")[-1])
    msg.set_content(body)
    server = smtp_connect(s)
    try:
        server.send_message(msg)
    except smtplib.SMTPRecipientsRefused:
        raise MailerError(f"The email server refused the address {to}.")
    except smtplib.SMTPException as e:
        raise MailerError(f"Sending failed: {e}")
    finally:
        try:
            server.quit()
        except Exception:
            pass
    log.append({"date": datetime.now().isoformat(timespec="seconds"), "to": to, "subject": subject,
                "channel": req.get("link", ""), "message_id": msg["Message-ID"]})
    write_json(SEND_LOG, log)
    return {"ok": True, "sent_today": sent_today(log), "limit": limit}


def test(_req):
    s = load_settings()
    smtp_connect(s).quit()
    return {"ok": True, "message": f"Signed in as {s['from_email']}. Nothing was sent."}


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    handlers = {"send": send, "test": test}
    if command not in handlers:
        print(json.dumps({"error": "usage: mailer.py send|test"}))
        sys.exit(2)
    try:
        req = json.loads(sys.stdin.read() or "{}")
        print(json.dumps(handlers[command](req)))
    except MailerError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    except Exception as e:  # never show a traceback in the dashboard
        print(json.dumps({"error": f"Unexpected problem: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
