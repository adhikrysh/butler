from garmin import human_age, summarize_activity


def test_human_age():
    assert human_age(90) == "1m"
    assert human_age(3700) == "1h01m"
    assert human_age(90000) == "1d"


ACT = {
    "activityId": 178654,
    "activityName": "Morning Run",
    "activityType": {"typeKey": "running"},
    "startTimeLocal": "2026-07-07 07:10:00",
    "distance": 10200.0,          # meters
    "duration": 3120.0,           # seconds
    "averageHR": 145, "maxHR": 168,
    "calories": 610,
    "aerobicTrainingEffect": 2.8, "anaerobicTrainingEffect": 0.4,
}


def test_summarize_activity():
    a = summarize_activity(ACT)
    assert a["garmin_activity_id"] == 178654
    assert a["type"] == "running"
    assert a["distance_km"] == 10.2
    assert a["duration_min"] == 52          # 3120s -> 52 min
    assert a["avg_hr"] == 145 and a["max_hr"] == 168
    assert a["calories"] == 610
    assert a["aerobic_te"] == 2.8
    assert a["start_time"] == "2026-07-07 07:10:00"


def test_summarize_activity_missing():
    a = summarize_activity({})
    assert a["garmin_activity_id"] is None
    assert a["distance_km"] is None
