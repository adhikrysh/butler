# /// script
# requires-python = ">=3.11"
# dependencies = ["garminconnect>=0.2.20", "tzdata"]
# ///
"""Pull a daily Garmin Connect snapshot via the API — no browser, no captcha.

Auth: resumes OAuth tokens from a token dir; if absent/expired it falls back to a
credentials login using GARMIN_EMAIL / GARMIN_PASSWORD and re-saves tokens. The
token dir lives in the butler profile and is never in git.

Lean by design: each run calls only the ~13 endpoints that feed the curated daily
stats (steps, sleep, HRV, readiness, recovery, respiration, SpO2, hydration,
weight, fitness age, endurance...) for yesterday + today. We do NOT archive raw
intraday firehoses (per-2-min HR/stress, minute-by-minute sleep) — Garmin retains
all of that on their servers, so any future intraday use-case can backfill the
exact day on demand instead of us photocopying it every morning.

Outputs:
  * state/history.jsonl  — one curated record appended per run (the trend log).
  * stdout (default)     — the curated JSON record (interactive skill / debugging).
  * stdout (--telegram)  — verbatim Telegram summary (for the --no-agent cron).
On failure: one-line reason to stderr + non-zero exit (empty stdout => cron silent).

Sync-gate (optional): if GARMIN_SYNC_CMD is set (or --sync is passed) the script
gates the pull on a confirmed-fresh watch upload. See lib/garmin.ensure_fresh_sync.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from garminconnect import Garmin

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from garmin import client, last_sync, ensure_fresh_sync, _safe  # noqa: E402
from garmincore import curate, telegram_summary, freshness_line  # noqa: E402

PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_DIR = Path(os.environ.get(
    "BUTLER_GARMIN_STATE", str(Path(__file__).resolve().parent.parent / "state")))


# Only the endpoints whose data lands in the curated stats below. Intraday-only
# endpoints (per-2-min HR/stress, minute sleep movement, etc.) are deliberately not
# called — Garmin keeps that history, so backfill on demand if a use-case needs it.
_DAILY = [
    ("user_summary",       lambda g, d: g.get_stats(d)),
    ("sleep",              lambda g, d: g.get_sleep_data(d)),
    ("hrv",                lambda g, d: g.get_hrv_data(d)),
    ("respiration",        lambda g, d: g.get_respiration_data(d)),
    ("spo2",               lambda g, d: g.get_spo2_data(d)),
    ("body_battery",       lambda g, d: g.get_body_battery(d, d)),
    ("training_readiness", lambda g, d: g.get_training_readiness(d)),
    ("training_status",    lambda g, d: g.get_training_status(d)),
    ("hydration",          lambda g, d: g.get_hydration_data(d)),
    ("fitness_age",        lambda g, d: g.get_fitnessage_data(d)),
    ("endurance_score",    lambda g, d: g.get_endurance_score(d)),
    ("body_composition",   lambda g, d: g.get_body_composition(d)),
    ("activities",         lambda g, d: g.get_activities_by_date(d, d)),
]


def _fetch_day(g: Garmin, d: str) -> dict:
    """Fetch the per-day endpoint responses (transient — used only to curate)."""
    return {key: _safe(fn, g, d) for key, fn in _DAILY}


def main() -> int:
    try:
        g = client()
    except Exception as exc:
        print(f"garmin auth failed: {exc}", file=sys.stderr)
        return 1
    _trigger = os.environ.get("GARMIN_SYNC_CMD")
    if _trigger or "--sync" in sys.argv[1:]:
        synced_fresh = ensure_fresh_sync(
            g, trigger_cmd=_trigger,
            timeout=int(os.environ.get("GARMIN_SYNC_TIMEOUT", "180")),
            poll=int(os.environ.get("GARMIN_SYNC_POLL", "15")),
            max_age=int(os.environ.get("GARMIN_SYNC_MAX_AGE", "1200")))
    else:
        synced_fresh = None
    today = datetime.now(PACIFIC).date()
    yday = today - timedelta(days=1)
    today_s, yday_s = today.isoformat(), yday.isoformat()
    try:
        stats = {ds: curate(_fetch_day(g, ds)) for ds in (yday_s, today_s)}
    except Exception as exc:
        print(f"garmin fetch failed: {exc}", file=sys.stderr)
        return 1
    head = today_s  # 9pm slot: today is the complete day
    sync_ms, device = last_sync(g)
    sync_dt = datetime.fromtimestamp(sync_ms / 1000, timezone.utc) if sync_ms else None
    record = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "garmin-connect-api",
        "headline_date": head,
        "last_sync_utc": sync_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if sync_dt else None,
        "device": device,
        "synced_fresh": synced_fresh,
        "stats": stats,
    }
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with (STATE_DIR / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"state write failed: {exc}", file=sys.stderr)
        return 1
    if "--telegram" in sys.argv[1:]:
        msg = telegram_summary(head, stats[head])
        sync_local = sync_dt.astimezone(PACIFIC) if sync_dt else None
        msg += "\n" + freshness_line(sync_local, datetime.now(PACIFIC), device=device)
        sys.stdout.write(msg + "\n")
    else:
        json.dump(record, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
