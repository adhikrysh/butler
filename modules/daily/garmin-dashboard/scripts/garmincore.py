"""Garmin daily-stats curation — pure functions (no I/O, no garminconnect)."""


def curate(raw: dict) -> dict:
    """Flatten fetched endpoint responses into clean daily stats. Missing -> None."""
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


def dur(secs) -> str | None:
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
    if dur(st.get("sleep_seconds")):
        score = f" (score {st['sleep_score']})" if st.get("sleep_score") else ""
        r2.append(f"Sleep {dur(st['sleep_seconds'])}{score}")
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


def freshness_line(last_sync_local, now_local, device=None, stale_hours=6) -> str:
    """Footer stating watch-sync freshness by ABSOLUTE time. Warns ONLY when the
    last upload is genuinely old (> stale_hours before the pull) — not on the
    common case where the FR955 auto-uploaded a bit outside a strict window.
    Replaces the old always-on '⚠️ sync not confirmed' noise. Inputs are aware
    datetimes in the same tz."""
    dev = f" ({device})" if device else ""
    if last_sync_local is None:
        return f"📡 Watch sync time unknown{dev}"
    t = last_sync_local.strftime("%-I:%M%p").lower()   # e.g. '8:09pm'
    # clamp: clock skew / rounded watch timestamps can put last_sync slightly
    # after now, which would otherwise render a negative "— -N min before this".
    mins = max(0.0, (now_local - last_sync_local).total_seconds() / 60)
    if mins <= stale_hours * 60:
        if mins < 90:
            return f"📡 Synced {t}{dev} — {int(mins)} min before this"
        return f"📡 Synced {t}{dev}"
    hrs = int(round(mins / 60))
    return f"⚠️ Last synced {t}{dev} — ~{hrs}h ago, today's numbers may be incomplete"
