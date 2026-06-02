# /// script
# requires-python = ">=3.11"
# dependencies = ["garminconnect>=0.2.20", "tzdata"]
# ///
"""Pull Garmin Connect daily stats via the API — no browser, no captcha.

Auth: resumes OAuth tokens from a token dir; if they're absent or expired it
falls back to a credentials login using GARMIN_EMAIL / GARMIN_PASSWORD from the
environment and re-saves the tokens. The token dir lives in the butler profile
and is never in git.

Default: prints one JSON record to stdout (interactive skill / debugging).
--telegram: prints the final, verbatim Telegram summary (for the --no-agent cron).
Either way it writes state/<pacific-date>.json and appends state/history.jsonl.
On failure: a one-line reason to stderr + non-zero exit (empty stdout => the
--no-agent cron stays silent for the day).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from garminconnect import Garmin

PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_DIR = Path(os.environ.get(
    "BUTLER_GARMIN_STATE", str(Path(__file__).resolve().parent.parent / "state")))
TOKEN_DIR = os.environ.get(
    "BUTLER_GARMIN_TOKENS", os.path.expanduser("~/.hermes/profiles/butler/garmin_tokens"))


def _client() -> Garmin:
    """Resume from saved tokens; else log in with .env creds and save tokens."""
    g = Garmin()
    try:
        g.login(TOKEN_DIR)
        return g
    except Exception:
        pass  # no/expired tokens -> credentials fallback below
    email, pw = os.environ.get("GARMIN_EMAIL"), os.environ.get("GARMIN_PASSWORD")
    if not (email and pw):
        raise RuntimeError("no saved tokens and GARMIN_EMAIL/GARMIN_PASSWORD not set")
    g = Garmin(email, pw)
    g.login()  # raises on rate-limit/MFA/captcha -> caught by caller, reported plainly
    Path(TOKEN_DIR).mkdir(parents=True, exist_ok=True)
    g.client.dump(TOKEN_DIR)  # persist OAuth tokens for future token-only resumes
    return g


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def _day(g: Garmin, d: str) -> dict:
    """Clean per-day stat dict. Missing metrics -> None (watch not worn / not synced)."""
    s = _safe(g.get_stats, d) or {}
    sleep = _safe(g.get_sleep_data, d) or {}
    sdto = (sleep.get("dailySleepDTO") or {}) if isinstance(sleep, dict) else {}
    hrv = _safe(g.get_hrv_data, d) or {}
    hrv_sum = (hrv.get("hrvSummary") or {}) if isinstance(hrv, dict) else {}

    def gv(*keys):
        for k in keys:
            if s.get(k) is not None:
                return s[k]
        return None

    sleep_secs = sdto.get("sleepTimeSeconds") or s.get("sleepingSeconds")
    scores = sdto.get("sleepScores") or {}
    sleep_score = (scores.get("overall") or {}).get("value") if isinstance(scores, dict) else None
    mod, vig = gv("moderateIntensityMinutes"), gv("vigorousIntensityMinutes")
    intensity = (mod or 0) + (vig or 0) if (mod is not None or vig is not None) else None
    return {
        "steps": gv("totalSteps"),
        "step_goal": gv("dailyStepGoal"),
        "resting_hr_bpm": gv("restingHeartRate"),
        "min_hr_bpm": gv("minHeartRate"),
        "max_hr_bpm": gv("maxHeartRate"),
        "calories_total": gv("totalKilocalories"),
        "calories_active": gv("activeKilocalories"),
        "floors_climbed": gv("floorsAscended"),
        "intensity_minutes": intensity,
        "moderate_intensity_min": mod,
        "vigorous_intensity_min": vig,
        "body_battery_recent": gv("bodyBatteryMostRecentValue"),
        "body_battery_high": gv("bodyBatteryHighestValue"),
        "body_battery_low": gv("bodyBatteryLowestValue"),
        "stress_avg": gv("averageStressLevel"),
        "stress_max": gv("maxStressLevel"),
        "sleep_seconds": sleep_secs,
        "sleep_score": sleep_score,
        "hrv_last_night_ms": hrv_sum.get("lastNightAvg"),
        "hrv_status": hrv_sum.get("status"),
    }


def _dur(secs) -> str | None:
    if not secs:
        return None
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


def telegram_summary(date_label: str, st: dict) -> str:
    lines = [f"🏃 Garmin — {date_label}"]
    r1 = []
    if st.get("steps") is not None:
        goal = f" (goal {st['step_goal']:,})" if st.get("step_goal") else ""
        r1.append(f"Steps {st['steps']:,}{goal}")
    if st.get("resting_hr_bpm") is not None:
        r1.append(f"Resting HR {st['resting_hr_bpm']} bpm")
    if r1:
        lines.append(" · ".join(r1))
    r2 = []
    if _dur(st.get("sleep_seconds")):
        score = f" (score {st['sleep_score']})" if st.get("sleep_score") else ""
        r2.append(f"Sleep {_dur(st['sleep_seconds'])}{score}")
    if st.get("body_battery_recent") is not None:
        r2.append(f"Body Battery {st['body_battery_recent']}")
    if r2:
        lines.append(" · ".join(r2))
    r3 = []
    if st.get("stress_avg") is not None:
        r3.append(f"Stress {st['stress_avg']} avg")
    if st.get("intensity_minutes") is not None:
        r3.append(f"Intensity {st['intensity_minutes']} min")
    if r3:
        lines.append(" · ".join(r3))
    if st.get("hrv_last_night_ms") is not None:
        status = f" ({st['hrv_status'].lower()})" if st.get("hrv_status") else ""
        lines.append(f"HRV {st['hrv_last_night_ms']} ms{status}")
    if len(lines) == 1:
        lines.append("No data synced yet.")
    return "\n".join(lines)


def main() -> int:
    try:
        g = _client()
    except Exception as exc:
        print(f"garmin auth failed: {exc}", file=sys.stderr)
        return 1
    today = datetime.now(PACIFIC).date()
    yday = today - timedelta(days=1)
    try:
        stats = {d.isoformat(): _day(g, d.isoformat()) for d in (yday, today)}
    except Exception as exc:
        print(f"garmin fetch failed: {exc}", file=sys.stderr)
        return 1
    # Headline the last *complete* day (yesterday) for the morning summary.
    head = yday.isoformat()
    record = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "garmin-connect-api",
        "headline_date": head,
        "stats": stats,
    }
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{today.isoformat()}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8")
        with (STATE_DIR / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"state write failed: {exc}", file=sys.stderr)
        return 1
    if "--telegram" in sys.argv[1:]:
        sys.stdout.write(telegram_summary(head, stats[head]) + "\n")
    else:
        json.dump(record, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
