"""Uptime monitor: checks that sites respond, emails on every check while a site is down,
and once more when it comes back up.

python uptime.py [--config uptime.json]
"""
import argparse
import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).parent
USER_AGENT = "Mozilla/5.0 (compatible; UptimeMonitor/1.0)"
TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 15


def log(message):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {message}", flush=True)


def probe(url):
    """Return None if the site is up, otherwise a short reason why it is down."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response.read(1024)
            return None
    except urllib.error.HTTPError as e:
        if e.code < 500:
            return None  # the server answered (e.g. 401/403/404), so it is up
        return f"HTTP {e.code} {e.reason}"
    except Exception as e:
        elapsed = time.monotonic() - started
        return f"{type(e).__name__}: {e} (after {elapsed:.0f}s)"


def check(url):
    """Probe twice before declaring a site down, to avoid alerts for one-off blips."""
    reason = probe(url)
    if reason:
        time.sleep(RETRY_DELAY_SECONDS)
        reason = probe(url)
    return reason


def send_email(to, subject, body):
    username = os.environ["SMTP_USERNAME"]
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = username
    message["To"] = ", ".join(to)
    message.set_content(body)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def main():
    parser = argparse.ArgumentParser(description="Email when websites go down.")
    parser.add_argument("--config", default=str(HERE / "uptime.json"))
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    state_path = config_path.parent / "snapshots" / "uptime-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for url in config["sites"]:
        reason = check(url)
        down_since = state.get(url)
        try:
            if reason:
                state[url] = down_since or now
                log(f"DOWN {url}: {reason}")
                send_email(
                    config["email_to"],
                    f"DOWN: {url}",
                    f"{url} is not responding.\n\nReason: {reason}\nDown since: {state[url]}\n"
                    f"Checked at: {now}\n\nYou will get this email on every check until it is back up.",
                )
            elif down_since:
                del state[url]
                log(f"BACK UP {url} (was down since {down_since})")
                send_email(
                    config["email_to"],
                    f"RECOVERED: {url}",
                    f"{url} is responding again.\n\nDown since: {down_since}\nBack up at: {now}\n",
                )
            else:
                log(f"up   {url}")
        except Exception as e:
            log(f"Email failed for {url}: {e}")

    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
