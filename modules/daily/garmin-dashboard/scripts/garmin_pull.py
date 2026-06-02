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

Sync-gate (optional): if GARMIN_SYNC_CMD is set (or --sync is passed) the script
first triggers a watch->cloud sync via that command, then blocks until Garmin's
cloud shows a newer device-upload timestamp than before the trigger (or until
GARMIN_SYNC_TIMEOUT). This makes the pulled data provably fresh instead of stale.
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
    """Deterministic sync-gate: fire a sync trigger, then block until the watch's
    cloud-upload timestamp advances past the pre-trigger baseline (proof a fresh
    upload landed), or until timeout. Returns True (confirmed fresh), False
    (timed out), or None (not attempted). Configured via env:
      GARMIN_SYNC_CMD     shell command that makes the phone foreground Garmin
                          Connect so it BLE-syncs the watch (e.g. an adb monkey
                          launch over Tailscale, or a Tasker HTTP hook).
      GARMIN_SYNC_TIMEOUT max seconds to wait for the upload to land (default 180)
      GARMIN_SYNC_POLL    seconds between cloud checks (default 15)
    """
    trigger = os.environ.get("GARMIN_SYNC_CMD")
    if not trigger and "--sync" not in sys.argv[1:]:
        return None
    timeout = int(os.environ.get("GARMIN_SYNC_TIMEOUT", "180"))
    poll = int(os.environ.get("GARMIN_SYNC_POLL", "15"))
    baseline = _last_sync(g)[0] or 0
    if trigger:
        try:
            subprocess.run(trigger, shell=True, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # best-effort; the gate below is the real guarantee
            print(f"sync trigger errored (continuing to poll): {exc}", file=sys.stderr)
    waited = 0
    while waited < timeout:
        current = _last_sync(g)[0] or 0
        if current > baseline:
            return True  # a newer upload reached the cloud
        time.sleep(poll)
        waited += poll
    return False  # no fresh upload within the window


def _day(g: Garmin, d: str) -> dict:
    """Clean per-day stat dict. Missing metrics -> None (watch not worn / not synced)."""
    s = _safe(g.get_stats, d) or {}
    sleep = _safe(g.get_sleep_data, d) or {}
    sdto = (sleep.get("dailySleepDTO") or {}) if isinstance(sleep, dict) else {}
    hrv = _safe(g.get_hrv_data, d) or {}
    hrv_sum = (hrv.get("hrvSummary") or {}) if isinstance(hrv, dict) else {}
    # Recovery / readiness / respiration / SpO2 / body-battery flux (extra endpoints).
    tr_list = _safe(g.get_training_readiness, d) or []
    tr = max(tr_list, key=lambda x: x.get("timestamp", "")) if isinstance(tr_list, list) and tr_list else {}
    ts = _safe(g.get_training_status, d) or {}
    vo2 = (ts.get("mostRecentVO2Max") or {}).get("generic") or {}
    lts = (ts.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
    ts_dev = next(iter(lts.values()), {}) if isinstance(lts, dict) else {}
    resp = _safe(g.get_respiration_data, d) or {}
    spo2 = _safe(g.get_spo2_data, d) or {}
    bb_list = _safe(g.get_body_battery, d, d) or []
    bb = bb_list[0] if isinstance(bb_list, list) and bb_list else {}

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
        "floors_climbed": round(gv("floorsAscended"), 1) if gv("floorsAscended") is not None else None,
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
        "spo2_latest": spo2.get("latestSpO2"),
        "body_battery_charged": bb.get("charged"),
        "body_battery_drained": bb.get("drained"),
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
    try:
        stats = {d.isoformat(): _day(g, d.isoformat()) for d in (yday, today)}
    except Exception as exc:
        print(f"garmin fetch failed: {exc}", file=sys.stderr)
        return 1
    # Headline the last *complete* day (yesterday) for the morning summary.
    head = yday.isoformat()
    sync_ms, device = _last_sync(g)
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
        (STATE_DIR / f"{today.isoformat()}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8")
        with (STATE_DIR / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
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
        json.dump(record, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
