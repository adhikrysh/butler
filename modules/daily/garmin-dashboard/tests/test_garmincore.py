from datetime import datetime

from garmincore import curate, dur, freshness_line, telegram_summary


def test_dur():
    assert dur(3661) == "1h01m"
    assert dur(0) is None
    assert dur(None) is None


RAW = {
    "user_summary": {
        "totalSteps": 8200, "dailyStepGoal": 8000, "restingHeartRate": 52,
        "totalKilocalories": 2600, "averageStressLevel": 30,
        "moderateIntensityMinutes": 20, "vigorousIntensityMinutes": 10,
        "bodyBatteryMostRecentValue": 65, "sleepingSeconds": 27000,
    },
    "sleep": {"dailySleepDTO": {"sleepTimeSeconds": 27000,
              "sleepScores": {"overall": {"value": 82}}}},
    "hrv": {"hrvSummary": {"lastNightAvg": 61, "status": "BALANCED"}},
    "training_readiness": [{"timestamp": "t1", "score": 74, "level": "HIGH"}],
    "training_status": {"mostRecentVO2Max": {"generic": {"vo2MaxPreciseValue": 52.0}}},
    "activities": [{"activityId": 1}, {"activityId": 2}],
}


def test_curate_flattens_key_fields():
    st = curate(RAW)
    assert st["steps"] == 8200
    assert st["resting_hr_bpm"] == 52
    assert st["intensity_minutes"] == 30      # 20 + 10
    assert st["sleep_score"] == 82
    assert st["hrv_last_night_ms"] == 61
    assert st["training_readiness"] == 74
    assert st["vo2max"] == 52.0
    assert st["activity_count"] == 2


def test_curate_missing_is_none():
    st = curate({})
    assert st["steps"] is None
    assert st["activity_count"] == 0          # no activities key -> [] -> 0 (verbatim behavior)


def test_telegram_summary_headers_and_rows():
    st = curate(RAW)
    msg = telegram_summary("2026-07-07", st)
    assert msg.startswith("🏃 Garmin — 2026-07-07")
    assert "Steps 8,200" in msg
    assert "Readiness 74" in msg
    assert "VO₂max 52.0" in msg


def test_telegram_summary_empty():
    assert "No data synced yet." in telegram_summary("2026-07-07", curate({}))


def test_freshness_recent_states_time_no_warning():
    line = freshness_line(datetime(2026, 7, 6, 20, 9), datetime(2026, 7, 6, 21, 0),
                          device="Forerunner 955")
    assert line.startswith("📡 Synced 8:09pm (Forerunner 955)")
    assert "51 min before" in line
    assert "⚠️" not in line


def test_freshness_moderate_gap_states_time_only():
    line = freshness_line(datetime(2026, 7, 6, 17, 0), datetime(2026, 7, 6, 21, 0))
    assert line == "📡 Synced 5:00pm"          # 4h < 6h stale threshold, >90min


def test_freshness_stale_warns():
    line = freshness_line(datetime(2026, 7, 6, 10, 0), datetime(2026, 7, 6, 21, 0))
    assert line.startswith("⚠️ Last synced 10:00am")
    assert "11h ago" in line


def test_freshness_unknown():
    assert "sync time unknown" in freshness_line(None, datetime(2026, 7, 6, 21, 0))


def test_freshness_boundary_90min_shows_time_only():
    # mins == 90 exactly: `< 90` is False -> time-only, no "min before"
    line = freshness_line(datetime(2026, 7, 6, 19, 30), datetime(2026, 7, 6, 21, 0))
    assert line == "📡 Synced 7:30pm"
    assert "min before" not in line


def test_freshness_boundary_exactly_stale_threshold_not_stale():
    # mins == stale_hours*60 (360) exactly: `<= 360` is True -> NOT stale
    line = freshness_line(datetime(2026, 7, 6, 15, 0), datetime(2026, 7, 6, 21, 0))
    assert line == "📡 Synced 3:00pm"
    assert "⚠️" not in line


def test_freshness_boundary_just_over_stale_threshold_warns():
    # mins == 361 (> 360): stale
    line = freshness_line(datetime(2026, 7, 6, 14, 59), datetime(2026, 7, 6, 21, 0))
    assert line.startswith("⚠️ Last synced 2:59pm")


def test_freshness_zero_gap_no_negative():
    # last_sync == now: 0 min, no negative number
    line = freshness_line(datetime(2026, 7, 6, 21, 0), datetime(2026, 7, 6, 21, 0))
    assert line == "📡 Synced 9:00pm — 0 min before this"
    assert "-" not in line


def test_freshness_skew_clamped_no_negative():
    # last_sync slightly AFTER now (clock skew): clamp to 0, never negative
    line = freshness_line(datetime(2026, 7, 6, 21, 10), datetime(2026, 7, 6, 21, 0))
    assert line == "📡 Synced 9:10pm — 0 min before this"
    assert "-10" not in line
