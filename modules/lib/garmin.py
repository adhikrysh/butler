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
from datetime import datetime, timedelta, timezone

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


# ---- session enrichment: fill a logged session from its Garmin activity ----

_CARDIO_TYPES = {"run", "ride", "swim"}

_TYPE_KEYWORDS = {
    "strength": ("strength",),
    "run": ("run",),
    "ride": ("cycl", "bik"),
    "swim": ("swim",),
    "mobility": ("yoga", "pilates", "mobility"),
}


def enrich_session(g, session, sync_cmd=None):
    """Best-effort: fill a logged session (any type, strength included) from
    its matching same-day Garmin activity.

    Matches by `session["garmin_activity_id"]` if set, else by a type ->
    activity-type-keyword lookup. The bare "day's only activity" fallback only
    applies to session types with NO keyword entry (e.g. sport/other) — for a
    mapped type (strength/run/ride/swim/mobility), an unmatched keyword search
    leaves the session unenriched rather than grabbing an unrelated same-day
    activity (e.g. an evening strength session must not inherit a morning
    run's HR/calories just because it's the day's only recorded activity).
    Fills `duration_min, avg_hr, max_hr, calories, aerobic_te, anaerobic_te`
    (+ `distance_km` for cardio types), only where the session field is
    currently empty. Never raises — on any failure the session is returned
    unchanged.
    """
    try:
        if sync_cmd:
            ensure_fresh_sync(g, trigger_cmd=sync_cmd)
        day = str(session.get("date") or "")[:10] or datetime.now(timezone.utc).astimezone().date().isoformat()
        acts = [summarize_activity(a) for a in activities(g, day, day)]
        want = session.get("garmin_activity_id")
        session_type = session.get("type")
        mapped = session_type in _TYPE_KEYWORDS
        kw = _TYPE_KEYWORDS.get(session_type, ())
        typed = [a for a in acts if any(k in str(a.get("type") or "").lower() for k in kw)]
        m = (next((a for a in acts if str(a["garmin_activity_id"]) == str(want)), None) if want
             else (typed[-1] if typed else (acts[0] if (len(acts) == 1 and not mapped) else None)))
        if m:
            session.setdefault("garmin_activity_id", m["garmin_activity_id"])
            fields = ["duration_min", "avg_hr", "max_hr", "calories", "aerobic_te", "anaerobic_te"]
            if session.get("type") in _CARDIO_TYPES:
                fields.append("distance_km")
            for k in fields:
                if not session.get(k) and m.get(k) is not None:
                    session[k] = m[k]
    except Exception:
        pass
    return session


def training_readiness(g, date_str):
    """Today's training readiness list (or [])."""
    return _safe(g.get_training_readiness, date_str) or []


# ---- coach_snapshot: best-effort recovery + fitness-trajectory + body read layer ----
#
# Every g.get_* call is wrapped in _safe (never raises). Every dict/list access
# defensively falls back to {}/[] so a surprising shape can't raise either.
# coach_snapshot() itself wraps each of the three groups so one group's total
# failure (a bug, not just a missing field) can't take the other two down.

def _latest_training_readiness(g, date_str):
    """Most recent training-readiness entry for the day (or {})."""
    tr_list = _safe(g.get_training_readiness, date_str)
    if not isinstance(tr_list, list) or not tr_list:
        return {}
    try:
        return max((x for x in tr_list if isinstance(x, dict)),
                    key=lambda x: x.get("timestamp", ""), default={})
    except Exception:
        return {}


def recovery_snapshot(g, date_str):
    """Readiness/body-battery/sleep/HRV/RHR/stress subset (mirrors
    garmin-dashboard's garmincore.curate() field paths)."""
    s = _safe(g.get_stats, date_str)
    s = s if isinstance(s, dict) else {}
    sleep = _safe(g.get_sleep_data, date_str)
    sleep = sleep if isinstance(sleep, dict) else {}
    sdto = sleep.get("dailySleepDTO")
    sdto = sdto if isinstance(sdto, dict) else {}
    hrv = _safe(g.get_hrv_data, date_str)
    hrv = hrv if isinstance(hrv, dict) else {}
    hrv_sum = hrv.get("hrvSummary")
    hrv_sum = hrv_sum if isinstance(hrv_sum, dict) else {}
    tr = _latest_training_readiness(g, date_str)
    sleep_scores = sdto.get("sleepScores")
    sleep_overall = sleep_scores.get("overall") if isinstance(sleep_scores, dict) else None

    return {
        "readiness_score": tr.get("score"),
        "readiness_level": tr.get("level"),
        "recovery_time_hours": tr.get("recoveryTime"),
        "body_battery_recent": s.get("bodyBatteryMostRecentValue"),
        "body_battery_high": s.get("bodyBatteryHighestValue"),
        "body_battery_low": s.get("bodyBatteryLowestValue"),
        "sleep_score": sleep_overall.get("value") if isinstance(sleep_overall, dict) else None,
        "hrv_last_night_ms": hrv_sum.get("lastNightAvg"),
        "hrv_status": hrv_sum.get("status"),
        "resting_hr_bpm": s.get("restingHeartRate"),
        "stress_avg": s.get("averageStressLevel"),
    }


def race_predictions(g):
    """Predicted race times (seconds) at 5K/10K/half/marathon distances."""
    r = _safe(g.get_race_predictions)
    r = r if isinstance(r, dict) else {}
    return {
        "5k_sec": r.get("time5K"),
        "10k_sec": r.get("time10K"),
        "half_marathon_sec": r.get("timeHalfMarathon"),
        "marathon_sec": r.get("timeMarathon"),
    }


def training_trajectory(g, date_str):
    """VO2max + training-status + load-balance feedback for the given date."""
    ts = _safe(g.get_training_status, date_str)
    ts = ts if isinstance(ts, dict) else {}

    vo2max = ts.get("mostRecentVO2Max")
    vo2 = (vo2max.get("generic") if isinstance(vo2max, dict) else None) or {}

    load_bal = ts.get("mostRecentTrainingLoadBalance")
    lb_map = (load_bal.get("metricsTrainingLoadBalanceDTOMap")
              if isinstance(load_bal, dict) else None) or {}
    lb = next(iter(lb_map.values()), {}) if isinstance(lb_map, dict) else {}
    lb = lb if isinstance(lb, dict) else {}

    status = ts.get("mostRecentTrainingStatus")
    lts = (status.get("latestTrainingStatusData") if isinstance(status, dict) else None) or {}
    ts_dev = next(iter(lts.values()), {}) if isinstance(lts, dict) else {}
    ts_dev = ts_dev if isinstance(ts_dev, dict) else {}

    return {
        "vo2max": vo2.get("vo2MaxPreciseValue") if vo2.get("vo2MaxPreciseValue") is not None else vo2.get("vo2MaxValue"),
        "training_status": ts_dev.get("trainingStatusFeedbackPhrase"),
        "load_balance": lb.get("trainingBalanceFeedbackPhrase"),
    }


def _latest_daily_weight_g(summaries):
    """Grams from the most-recent dailyWeightSummaries entry, or None.

    NOTE: the exact per-day key hasn't been live-verified (no weigh-ins logged
    yet) — defensively try the likely shapes (mirrors the Garmin Connect
    weight-history payload) and confirm/adjust once a real weigh-in exists.
    """
    if not isinstance(summaries, list) or not summaries:
        return None
    try:
        latest = max(
            (s for s in summaries if isinstance(s, dict)),
            key=lambda s: str(s.get("summaryDate", "")), default=None)
    except Exception:
        return None
    if not isinstance(latest, dict):
        return None
    lw = latest.get("latestWeight")
    if isinstance(lw, dict) and isinstance(lw.get("weight"), (int, float)):
        return lw["weight"]
    if isinstance(latest.get("weight"), (int, float)):
        return latest["weight"]
    metrics = latest.get("allWeightMetrics")
    if isinstance(metrics, list) and metrics:
        last = metrics[-1]
        if isinstance(last, dict) and isinstance(last.get("weight"), (int, float)):
            return last["weight"]
    return None


def weight_series(g, date_str, days=30):
    """Weight trend over the trailing `days` window ending on date_str.

    `latest_kg` is the TRUE most-recent weigh-in (from the last
    dailyWeightSummaries entry); `avg_30d_kg` is the range average Garmin
    reports for the window. Callers wanting "current weight" should use
    `latest_kg`, not `avg_30d_kg`.
    """
    try:
        end_dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_str = (end_dt - timedelta(days=days)).strftime("%Y-%m-%d")
    except Exception:
        start_str = date_str

    w = _safe(g.get_weigh_ins, start_str, date_str)
    w = w if isinstance(w, dict) else {}
    avg = w.get("totalAverage")
    avg = avg if isinstance(avg, dict) else {}
    avg_weight_g = avg.get("weight")
    trend = w.get("dailyWeightSummaries")
    trend = trend if isinstance(trend, list) else []
    latest_weight_g = _latest_daily_weight_g(trend)

    return {
        "latest_kg": round(latest_weight_g / 1000, 1) if isinstance(latest_weight_g, (int, float)) else None,
        "avg_30d_kg": round(avg_weight_g / 1000, 1) if isinstance(avg_weight_g, (int, float)) else None,
        "trend": trend,
    }


def log_weight(g, kg, ts=None) -> dict:
    """Best-effort: write a weigh-in to Garmin (kg). Never raises.

    `ts` is an optional ISO-format timestamp string; Garmin defaults to "now"
    when omitted. Returns {"ok": True, "kg": kg} on success or
    {"ok": False, "error": str(exc)} on any failure (never propagates).
    """
    try:
        g.add_weigh_in(weight=kg, unitKey="kg", timestamp=ts or "")
        return {"ok": True, "kg": kg}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---- programme -> watch: named workout + description (honest degradation) ----
#
# Garmin's structured-workout schema can encode running/cycling steps cleanly,
# but strength is modeled loosely (sets/reps aren't first-class there in a way
# worth faking). Rather than force strength into a fake structured shape, we
# push ONE minimal valid step and put the day's real plan in the description —
# honest, readable on the watch/app, and fully reversible (unschedule/delete).

_SPORT = {
    "running": {"sportTypeId": 1, "sportTypeKey": "running"},
    "strength": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
    "cycling": {"sportTypeId": 2, "sportTypeKey": "cycling"},
}


def build_workout(name, sport_key, description) -> dict:
    """A minimal valid Garmin workout: one open (lap-button) step, the day's
    plan carried in `description`. No faked structured-strength precision."""
    sport = _SPORT.get(sport_key, _SPORT["strength"])
    return {
        "workoutName": (name or "")[:80],
        "description": (description or "")[:1024],
        "sportType": sport,
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": sport,
            "workoutSteps": [{
                "type": "ExecutableStepDTO",
                "stepOrder": 1,
                "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                "endCondition": {"conditionTypeId": 1, "conditionTypeKey": "lap.button"},
                "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
            }],
        }],
    }


def push_workout(g, name, sport_key, description) -> dict:
    """Best-effort: upload a named workout (plan in description). Never raises.

    Returns {"ok": True, "workout_id": <id>} or {"ok": False, "error": str}.
    """
    try:
        res = g.upload_workout(build_workout(name, sport_key, description))
        wid = (res or {}).get("workoutId") if isinstance(res, dict) else None
        return {"ok": True, "workout_id": wid}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def schedule(g, workout_id, date_str) -> dict:
    """Best-effort: schedule an uploaded workout on a date. Never raises."""
    try:
        res = g.schedule_workout(workout_id, date_str)
        return {"ok": True, "result": res}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def unschedule(g, scheduled_id) -> dict:
    """Best-effort: remove a scheduled workout occurrence. Never raises."""
    try:
        res = g.unschedule_workout(scheduled_id)
        return {"ok": True, "result": res}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def delete_workout(g, workout_id) -> dict:
    """Best-effort: delete a workout definition entirely. Never raises."""
    try:
        res = g.delete_workout(workout_id)
        return {"ok": True, "result": res}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def garmin_prs(g):
    """Personal records as [{"type_id": ..., "value": ...}, ...].

    `prTypeLabelKey` comes back null live, so it's dropped rather than
    shipping an unreliable/always-null "label" field.
    """
    prs = _safe(g.get_personal_record)
    if not isinstance(prs, list):
        return []
    return [{"type_id": p.get("typeId"), "value": p.get("value")}
            for p in prs if isinstance(p, dict)]


def _group(fn, *a):
    """Run one coach_snapshot group; never let it take the others down."""
    try:
        result = fn(*a)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _fitness_snapshot(g, date_str):
    return {**training_trajectory(g, date_str), "race_predictions": race_predictions(g)}


def _body_snapshot(g, date_str):
    return {**weight_series(g, date_str), "prs": garmin_prs(g)}


def coach_snapshot(g, date_str):
    """Best-effort coaching read: recovery + fitness trajectory + body/records.

    Never raises, even if every underlying Garmin call throws — each group
    degrades to {} independently so a Garmin outage never blanks the whole
    picture.
    """
    return {
        "recovery": _group(recovery_snapshot, g, date_str),
        "fitness": _group(_fitness_snapshot, g, date_str),
        "body": _group(_body_snapshot, g, date_str),
    }
