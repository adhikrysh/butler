# /// script
# requires-python = ">=3.11"
# dependencies = ["garminconnect>=0.2.20", "tzdata"]
# ///
"""Pull Garmin Connect daily stats via the API — no browser, no captcha.

Auth: resumes OAuth tokens from a token dir; if absent/expired it falls back to a
credentials login using GARMIN_EMAIL / GARMIN_PASSWORD and re-saves tokens. The
token dir lives in the butler profile and is never in git.

Captures EVERYTHING: each run hits ~24 per-day endpoints (+ 3 account-level ones)
for yesterday and today and stores their **raw** responses, so no field is lost
for future downstream use. A curated `stats` subset is derived from that raw (no
extra API calls) for the Telegram summary and quick querying.

Outputs:
  * state/<today>.json    — FULL record incl. raw responses (the complete archive).
  * state/history.jsonl   — CURATED record per run (lean, queryable trend log).
  * stdout (default)      — CURATED JSON (for the interactive skill / debugging).
  * stdout (--telegram)   — verbatim Telegram summary (for the --no-agent cron).
On failure: one-line reason to stderr + non-zero exit (empty stdout => cron silent).

Sync-gate (optional): if GARMIN_SYNC_CMD is set (or --sync is passed) the script
gates the pull on a confirmed-fresh watch upload — either firing a trigger and
waiting for the cloud upload time to advance, or (gate-only --sync) confirming the
last upload is recent. See _wait_for_fresh_sync.
"""
import json
import os
import subprocess
import sys
import time
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


def _last_sync(g: Garmin):
    """When the watch last uploaded to Garmin's cloud: (epoch_ms, device_name)."""
    info = _safe(g.get_device_last_used) or {}
    if not isinstance(info, dict):
        return None, None
    return info.get("lastUsedDeviceUploadTime"), info.get("lastUsedDeviceName")


def _human_age(seconds: float) -> str:
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"
    return f"{s // 86400}d"


def _wait_for_fresh_sync(g: Garmin) -> bool | None:
    """Gate the pull on a confirmed-fresh watch upload. Returns True (fresh),
    False (timed out), or None (not attempted). Enabled by GARMIN_SYNC_CMD or --sync.

    Two modes:
      * Trigger mode (GARMIN_SYNC_CMD set): fire the command to make the phone sync the
        watch, then wait until the cloud upload timestamp advances past the pre-trigger
        baseline — proof THIS sync landed.
      * Gate-only mode (--sync, no command): the sync is triggered elsewhere (e.g. an
        iPhone Shortcut opens Garmin Connect at 07:55, a few min before this 08:00 run),
        so just confirm the last upload is recent — within GARMIN_SYNC_MAX_AGE — polling
        until it is or until GARMIN_SYNC_TIMEOUT.
    Env: GARMIN_SYNC_TIMEOUT=180, GARMIN_SYNC_POLL=15, GARMIN_SYNC_MAX_AGE=1200 (secs).
    """
    trigger = os.environ.get("GARMIN_SYNC_CMD")
    if not trigger and "--sync" not in sys.argv[1:]:
        return None
    timeout = int(os.environ.get("GARMIN_SYNC_TIMEOUT", "180"))
    poll = int(os.environ.get("GARMIN_SYNC_POLL", "15"))
    max_age = int(os.environ.get("GARMIN_SYNC_MAX_AGE", "1200"))
    baseline = _last_sync(g)[0] or 0
    if trigger:
        try:
            subprocess.run(trigger, shell=True, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # best-effort; the gate below is the real guarantee
            print(f"sync trigger errored (continuing to poll): {exc}", file=sys.stderr)
    waited = 0
    while True:
        ts = _last_sync(g)[0] or 0
        if trigger:
            if ts > baseline:
                return True  # the sync we triggered reached the cloud
        elif ts and (datetime.now(timezone.utc).timestamp() - ts / 1000) <= max_age:
            return True  # last upload is recent enough (Shortcut already synced it)
        if waited >= timeout:
            return False
        time.sleep(poll)
        waited += poll


# --- comprehensive capture ---------------------------------------------------
# Per-day endpoints (key -> g.method(date)). Signatures verified live against the
# installed garminconnect; every one returns data (or an empty/None payload when
# the metric isn't recorded that day). Raw responses are archived verbatim.
_DAILY = [
    ("user_summary",        lambda g, d: g.get_stats(d)),
    ("sleep",               lambda g, d: g.get_sleep_data(d)),
    ("hrv",                 lambda g, d: g.get_hrv_data(d)),
    ("stress",              lambda g, d: g.get_stress_data(d)),
    ("respiration",         lambda g, d: g.get_respiration_data(d)),
    ("spo2",                lambda g, d: g.get_spo2_data(d)),
    ("heart_rate",          lambda g, d: g.get_heart_rates(d)),
    ("resting_hr",          lambda g, d: g.get_rhr_day(d)),
    ("steps_intraday",      lambda g, d: g.get_steps_data(d)),
    ("floors",              lambda g, d: g.get_floors(d)),
    ("intensity_minutes",   lambda g, d: g.get_intensity_minutes_data(d)),
    ("hydration",           lambda g, d: g.get_hydration_data(d)),
    ("body_battery",        lambda g, d: g.get_body_battery(d, d)),
    ("body_battery_events", lambda g, d: g.get_body_battery_events(d)),
    ("training_readiness",  lambda g, d: g.get_training_readiness(d)),
    ("training_status",     lambda g, d: g.get_training_status(d)),
    ("max_metrics",         lambda g, d: g.get_max_metrics(d)),
    ("endurance_score",     lambda g, d: g.get_endurance_score(d)),
    ("hill_score",          lambda g, d: g.get_hill_score(d)),
    ("fitness_age",         lambda g, d: g.get_fitnessage_data(d)),
    ("running_tolerance",   lambda g, d: g.get_running_tolerance(d, d)),
    ("activities",          lambda g, d: g.get_activities_by_date(d, d)),
    ("body_composition",    lambda g, d: g.get_body_composition(d)),
    ("blood_pressure",      lambda g, d: g.get_blood_pressure(d, d)),
]

# Account-level snapshots (not per-day) — captured once per run.
_ACCOUNT = [
    ("race_predictions",  lambda g: g.get_race_predictions()),
    ("lactate_threshold", lambda g: g.get_lactate_threshold()),
    ("personal_records",  lambda g: g.get_personal_record()),
]


def _capture_raw(g: Garmin, d: str) -> dict:
    """Every per-day endpoint's raw response for date d (None on per-endpoint error)."""
    return {key: _safe(fn, g, d) for key, fn in _DAILY}


def _capture_account(g: Garmin) -> dict:
    return {key: _safe(fn, g) for key, fn in _ACCOUNT}


def _curate(raw: dict) -> dict:
    """Derive a clean, flat stat dict from the raw responses (no extra API calls).
    Missing metric -> None (watch not worn, sensor off, or not synced)."""
    s = raw.get("user_summary") or {}
    sleep = raw.get("sleep") or {}
    sdto = (sleep.get("dailySleepDTO") or {}) if isinstance(sleep, dict) else {}
    hrv = raw.get("hrv") or {}
    hrv_sum = (hrv.get("hrvSummary") or {}) if isinstance(hrv, dict) else {}
    tr_list = raw.get("training_readiness") or []
    tr = max(tr_list, key=lambda x: x.get("timestamp", "")) if isinstance(tr_list, list) and tr_list else {}
    ts = raw.get("training_status") or {}
    vo2 = (ts.get("mostRecentVO2Max") or {}).get("generic") or {}
    lts = (ts.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
    ts_dev = next(iter(lts.values()), {}) if isinstance(lts, dict) else {}
    resp = raw.get("respiration") or {}
    spo2 = raw.get("spo2") or {}
    bb_list = raw.get("body_battery") or []
    bb = bb_list[0] if isinstance(bb_list, list) and bb_list else {}
    hyd = raw.get("hydration") or {}
    fage = raw.get("fitness_age") or {}
    endur = raw.get("endurance_score") or {}
    bc = raw.get("body_composition") or {}
    bc_avg = (bc.get("totalAverage") or {}) if isinstance(bc, dict) else {}
    activities = raw.get("activities") or []

    def gv(*keys):
        for k in keys:
            if s.get(k) is not None:
                return s[k]
        return None

    floors = gv("floorsAscended")
    mod, vig = gv("moderateIntensityMinutes"), gv("vigorousIntensityMinutes")
    intensity = (mod or 0) + (vig or 0) if (mod is not None or vig is not None) else None
    weight_g = bc_avg.get("weight")
    return {
        "steps": gv("totalSteps"),
        "step_goal": gv("dailyStepGoal"),
        "distance_m": gv("totalDistanceMeters"),
        "resting_hr_bpm": gv("restingHeartRate"),
        "min_hr_bpm": gv("minHeartRate"),
        "max_hr_bpm": gv("maxHeartRate"),
        "calories_total": gv("totalKilocalories"),
        "calories_active": gv("activeKilocalories"),
        "calories_bmr": gv("bmrKilocalories"),
        "floors_climbed": round(floors, 1) if floors is not None else None,
        "intensity_minutes": intensity,
        "moderate_intensity_min": mod,
        "vigorous_intensity_min": vig,
        "body_battery_recent": gv("bodyBatteryMostRecentValue"),
        "body_battery_high": gv("bodyBatteryHighestValue"),
        "body_battery_low": gv("bodyBatteryLowestValue"),
        "body_battery_charged": bb.get("charged"),
        "body_battery_drained": bb.get("drained"),
        "stress_avg": gv("averageStressLevel"),
        "stress_max": gv("maxStressLevel"),
        "sleep_seconds": sdto.get("sleepTimeSeconds") or s.get("sleepingSeconds"),
        "sleep_score": ((sdto.get("sleepScores") or {}).get("overall") or {}).get("value"),
        "sleep_deep_seconds": sdto.get("deepSleepSeconds"),
        "sleep_light_seconds": sdto.get("lightSleepSeconds"),
        "sleep_rem_seconds": sdto.get("remSleepSeconds"),
        "sleep_awake_seconds": sdto.get("awakeSleepSeconds"),
        "hrv_last_night_ms": hrv_sum.get("lastNightAvg"),
        "hrv_status": hrv_sum.get("status"),
        "training_readiness": tr.get("score"),
        "training_readiness_level": tr.get("level"),
        "recovery_time_hours": tr.get("recoveryTime"),
        "vo2max": vo2.get("vo2MaxPreciseValue") or vo2.get("vo2MaxValue"),
        "training_status": ts_dev.get("trainingStatusFeedbackPhrase"),
        "respiration_avg_waking": resp.get("avgWakingRespirationValue"),
        "respiration_avg_sleep": resp.get("avgSleepRespirationValue"),
        "respiration_low": resp.get("lowestRespirationValue"),
        "respiration_high": resp.get("highestRespirationValue"),
        "spo2_avg": spo2.get("averageSpO2"),
        "spo2_lowest": spo2.get("lowestSpO2"),
        "hydration_ml": hyd.get("valueInML"),
        "hydration_goal_ml": hyd.get("goalInML"),
        "weight_kg": round(weight_g / 1000, 1) if weight_g else None,
        "fitness_age": fage.get("fitnessAge"),
        "endurance_score": endur.get("overallScore"),
        "activity_count": len(activities) if isinstance(activities, list) else None,
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
    if st.get("training_readiness") is not None:
        lvl = f" ({st['training_readiness_level'].title()})" if st.get("training_readiness_level") else ""
        vo2 = f" · VO₂max {st['vo2max']}" if st.get("vo2max") else ""
        lines.append(f"Readiness {st['training_readiness']}{lvl}{vo2}")
    r4 = []
    if st.get("respiration_avg_waking") is not None:
        r4.append(f"Respiration {st['respiration_avg_waking']} br/min")
    if st.get("spo2_avg") is not None:
        r4.append(f"SpO₂ {st['spo2_avg']}%")
    if r4:
        lines.append(" · ".join(r4))
    r5 = []
    if st.get("weight_kg") is not None:
        r5.append(f"Weight {st['weight_kg']} kg")
    if st.get("hydration_ml") is not None:
        r5.append(f"Hydration {round(st['hydration_ml'])} ml")
    if r5:
        lines.append(" · ".join(r5))
    if len(lines) == 1:
        lines.append("No data synced yet.")
    return "\n".join(lines)


def main() -> int:
    try:
        g = _client()
    except Exception as exc:
        print(f"garmin auth failed: {exc}", file=sys.stderr)
        return 1
    # Optional deterministic sync-gate: trigger a watch->cloud sync and wait for it
    # to land before pulling, so the data is provably fresh (not yesterday's).
    synced_fresh = _wait_for_fresh_sync(g)
    today = datetime.now(PACIFIC).date()
    yday = today - timedelta(days=1)
    today_s, yday_s = today.isoformat(), yday.isoformat()
    try:
        raw = {ds: _capture_raw(g, ds) for ds in (yday_s, today_s)}
        account = _capture_account(g)
    except Exception as exc:
        print(f"garmin fetch failed: {exc}", file=sys.stderr)
        return 1
    stats = {ds: _curate(raw[ds]) for ds in (yday_s, today_s)}
    head = yday_s  # last complete day for the morning summary
    sync_ms, device = _last_sync(g)
    sync_dt = datetime.fromtimestamp(sync_ms / 1000, timezone.utc) if sync_ms else None

    base = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "garmin-connect-api",
        "headline_date": head,
        "last_sync_utc": sync_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if sync_dt else None,
        "device": device,
        "synced_fresh": synced_fresh,
    }
    curated = {**base, "stats": stats}            # lean: for stdout, history, skill
    full = {**curated, "raw": raw, "account": account}  # complete archive: per-day file
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{today_s}.json").write_text(json.dumps(full, indent=2), encoding="utf-8")
        with (STATE_DIR / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(curated) + "\n")
    except OSError as exc:
        print(f"state write failed: {exc}", file=sys.stderr)
        return 1
    if "--telegram" in sys.argv[1:]:
        msg = telegram_summary(head, stats[head])
        if sync_dt:
            age = _human_age((datetime.now(timezone.utc) - sync_dt).total_seconds())
            msg += f"\n📡 Watch last synced {age} ago" + (f" ({device})" if device else "")
        if synced_fresh is False:
            msg += "  ⚠️ sync not confirmed"
        sys.stdout.write(msg + "\n")
    else:
        json.dump(curated, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
