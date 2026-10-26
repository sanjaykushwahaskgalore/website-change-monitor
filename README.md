# Site Watcher

Checks a list of web pages, works out what changed since the last check, and notifies people on Slack or by email. An optional AI review step uses Claude to decide whether a change matters and to summarise it in plain English.

## How it works

1. **Fetch.** Downloads each page and keeps only the visible text, dropping scripts and styles. If you give a CSS `selector`, only that part of the page is kept.
2. **Clean.** Drops lines that match your `ignore` patterns, such as timestamps or "5 minutes ago".
3. **Compare.** Compares the text with the snapshot saved last time in `snapshots/`. The first run only saves a baseline.
4. **Review (optional).** Claude reads the changed lines and your `watch_for` note, decides whether it is worth alerting anyone, and writes a short summary.
5. **Notify.** Prints the change, posts it to Slack and/or emails it, and appends it to `snapshots/changes.log`.

## Setup

```bash
pip install beautifulsoup4 anthropic
```

`anthropic` is only needed if you turn on `ai_review`.

## Configure `sites.json`

| Field | Meaning |
|---|---|
| `name` | Label used in alerts and for the snapshot file |
| `url` | Page to watch |
| `selector` | Optional CSS selector to watch just one part of the page, e.g. `main`, `#pricing`, `.job-list` |
| `ignore` | Optional regex patterns; lines that match are skipped (stops timestamps and counters causing false alerts) |
| `watch_for` | Optional plain-English note for the AI review, e.g. "price or plan changes", "new job postings" |
| `ai_review` (top level) | `true` to have Claude filter out noise and summarise changes |
| `notify.email` | SMTP settings for email alerts; set `"enabled": true` to use them |

Secrets go in environment variables, not in the file:

| Variable | Used for |
|---|---|
| `SLACK_WEBHOOK_URL` | A Slack incoming-webhook URL; if it is set, alerts go to that channel |
| `SMTP_USERNAME` | The sending email address (e.g. a Gmail address), if not set in `sites.json` |
| `SMTP_PASSWORD` | Password or app password for the email account |

On GitHub, these are repository secrets (Settings → Secrets and variables → Actions). The workflow in `.github/workflows/watch.yml` runs daily at 09:00 IST and can also be started by hand from the Actions tab.
| `ANTHROPIC_API_KEY` | Needed when `ai_review` is on |

## Run it

Check once (for a scheduler):

```bash
python watch.py
```

Keep running and check every 15 minutes:

```bash
python watch.py --every 15
```

Use a different config file:

```bash
python watch.py --config other-sites.json
```

## Run it on a schedule

- **Windows Task Scheduler:** create a task that runs `python C:\path\to\watch.py` every 15–60 minutes.
- **Linux/macOS cron:** `*/30 * * * * cd /path/to/site-watcher && python3 watch.py`
- **GitHub Actions (no server needed):** a scheduled workflow (`on: schedule: - cron: "*/30 * * * *"`) that runs the script and commits `snapshots/` back to the repo so the next run can compare.

## Limitations

- Pages that build their content with JavaScript can come back nearly empty. For those, swap `urllib` in `fetch_text` for a headless browser such as Playwright.
- Pages behind a login need cookies or an API instead.
- Be polite: check every 15 minutes or less often, and respect each site's terms of use.
- The AI review sees page text. A page could include text that tries to sway the verdict, so for high-stakes monitoring keep `ai_review` off or still log every change, which `changes.log` already does.
