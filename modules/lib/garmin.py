"""Shared Garmin client for the butler modules — auth + fetch + pure helpers.

garmin-dashboard (daily stats) and jim (per-activity coaching) both use this.
`garminconnect` is imported LAZILY inside client() so the pure helpers
(human_age, summarize_activity) import without the dependency (mirrors how
sheets.py defers gspread). Auth resumes OAuth tokens, else falls back to
GARMIN_EMAIL / GARMIN_PASSWORD and re-saves. The trigger command for on-demand
sync is a PARAMETER, never read from a hardcoded env var — callers choose their
own scope (garmin-dashboard: GARMIN_SYNC_CMD; jim: JIM_SYNC_CMD).
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

TOKEN_DIR = os.environ.get(
    "BUTLER_GARMIN_TOKENS", os.path.expanduser("~/.hermes/profiles/butler/garmin_tokens"))


# ---- pure helpers (no network, no garminconnect) ----

def human_age(seconds: float) -> str:
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"
    return f"{s // 86400}d"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def summarize_activity(a: dict) -> dict:
    """Map one Garmin activity JSON to a clean, coach-friendly record."""
    dist = _num(a.get("distance"))
    secs = _num(a.get("duration"))
    return {
        "garmin_activity_id": a.get("activityId"),
        "name": a.get("activityName"),
        "type": ((a.get("activityType") or {}).get("typeKey")),
        "start_time": a.get("startTimeLocal"),
        "distance_km": round(dist / 1000, 2) if dist else None,
        "duration_min": int(round(secs / 60)) if secs else None,
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "calories": a.get("calories"),
        "aerobic_te": a.get("aerobicTrainingEffect"),
        "anaerobic_te": a.get("anaerobicTrainingEffect"),
    }


# ---- network layer (garminconnect imported lazily) ----

def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def client():
    """Resume from saved tokens; else log in with .env creds and save tokens."""
    from garminconnect import Garmin
    g = Garmin()
    try:
        g.login(TOKEN_DIR)
        return g
    except Exception:
        pass
    email, pw = os.environ.get("GARMIN_EMAIL"), os.environ.get("GARMIN_PASSWORD")
    if not (email and pw):
        raise RuntimeError("no saved tokens and GARMIN_EMAIL/GARMIN_PASSWORD not set")
    g = Garmin(email, pw)
    g.login()
    from pathlib import Path
    Path(TOKEN_DIR).mkdir(parents=True, exist_ok=True)
    g.client.dump(TOKEN_DIR)
    return g


def last_sync(g):
    """(epoch_ms, device_name) of the watch's last cloud upload."""
    info = _safe(g.get_device_last_used) or {}
    if not isinstance(info, dict):
        return None, None
    return info.get("lastUsedDeviceUploadTime"), info.get("lastUsedDeviceName")


def ensure_fresh_sync(g, *, trigger_cmd=None, timeout=60, poll=10, max_age=1200):
    """Best-effort: make sure the latest watch data is on the cloud.

    trigger_cmd set -> fire it (e.g. Pushcut opens Garmin Connect), then poll
    until the upload timestamp advances past baseline (proof THIS sync landed).
    trigger_cmd None -> gate-only: return True once the last upload is recent
    (<= max_age). Returns True (fresh) / False (timed out) / None (nothing to do).
    """
    baseline = last_sync(g)[0] or 0
    if trigger_cmd:
        try:
            subprocess.run(trigger_cmd, shell=True, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            print(f"sync trigger errored (continuing to poll): {exc}", file=sys.stderr)
    waited = 0
    while True:
        ts = last_sync(g)[0] or 0
        if trigger_cmd:
            if ts > baseline:
                return True
        elif ts and (datetime.now(timezone.utc).timestamp() - ts / 1000) <= max_age:
            return True
        if waited >= timeout:
            return False
        time.sleep(poll)
        waited += poll


def activities(g, start_date, end_date):
    """Raw Garmin activities between two ISO dates (inclusive)."""
    return _safe(g.get_activities_by_date, start_date, end_date) or []


def activity_detail(g, activity_id):
    """Full detail for one activity (splits, HR zones, etc.)."""
    return _safe(g.get_activity, activity_id) or {}


def training_readiness(g, date_str):
    """Today's training readiness list (or [])."""
    return _safe(g.get_training_readiness, date_str) or []
