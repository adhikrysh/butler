import garmin


class FakeG:
    def get_race_predictions(self): return {"time5K":1500,"time10K":3200,"timeHalfMarathon":7000,"timeMarathon":15000,"calendarDate":"2026-07-08"}
    def get_training_status(self, d): return {"mostRecentVO2Max":{"generic":{"vo2MaxPreciseValue":52.3}},
        "mostRecentTrainingLoadBalance":{"metricsTrainingLoadBalanceDTOMap":{"x":{"trainingBalanceFeedbackPhrase":"BALANCED"}}},
        "mostRecentTrainingStatus":{"latestTrainingStatusData":{"dev1":{"trainingStatusFeedbackPhrase":"PRODUCTIVE_1"}}}}
    def get_weigh_ins(self, s, e): return {"totalAverage":{"weight":68500.0}, "dailyWeightSummaries":[
        {"summaryDate":"2026-07-01","latestWeight":{"weight":69000.0}},
        {"summaryDate":"2026-07-08","latestWeight":{"weight":68200.0}}]}
    def get_personal_record(self): return [{"typeId":1,"activityType":"running","value":1490,"prTypeLabelKey":"PR_5K"}]


def test_race_predictions():
    r = garmin.race_predictions(FakeG())
    assert r["5k_sec"] == 1500 and r["marathon_sec"] == 15000


def test_training_trajectory():
    t = garmin.training_trajectory(FakeG(), "2026-07-08")
    assert t["vo2max"] == 52.3
    assert t["training_status"] == "PRODUCTIVE_1"
    assert t["load_balance"] == "BALANCED"


def test_weight_series_grams_to_kg():
    w = garmin.weight_series(FakeG(), "2026-07-08")
    assert w["latest_kg"] == 68.2   # true latest (most-recent dailyWeightSummaries entry)
    assert w["avg_30d_kg"] == 68.5  # the old "totalAverage" range average


def test_garmin_prs():
    p = garmin.garmin_prs(FakeG())
    assert p[0] == {"type_id": 1, "value": 1490}
    assert "label" not in p[0]


def test_coach_snapshot_groups_and_never_raises():
    class Boom:
        def __getattr__(self, n):
            def f(*a, **k): raise RuntimeError("garmin down")
            return f
    snap = garmin.coach_snapshot(Boom(), "2026-07-08")
    assert set(snap.keys()) == {"recovery","fitness","body"}   # degrades, doesn't raise


class FakeStrengthG:
    def get_activities_by_date(self, start, end):
        return [{
            "activityId": 555,
            "activityName": "Strength",
            "activityType": {"typeKey": "strength_training"},
            "startTimeLocal": "2026-07-08 07:00:00",
            "duration": 3000,
            "averageHR": 121,
            "maxHR": 150,
            "calories": 310,
            "aerobicTrainingEffect": 1.8,
            "anaerobicTrainingEffect": 2.4,
        }]


def test_enrich_session_fills_strength_from_garmin():
    session = {"type": "strength", "date": "2026-07-08"}
    enriched = garmin.enrich_session(FakeStrengthG(), session)
    assert enriched is session
    assert enriched["avg_hr"] == 121
    assert enriched["calories"] == 310


def test_enrich_session_never_raises_on_client_failure():
    # get_activities_by_date SUCCEEDS (so `_safe`'s inner except never fires)
    # but returns a malformed activity (not a dict) so summarize_activity's
    # a.get(...) call raises inside the list comprehension in enrich_session
    # itself -- this exercises enrich_session's OWN outer try/except, not
    # just `_safe`'s.
    class Boom:
        def get_activities_by_date(self, start, end):
            return [42]
    session = {"type": "strength", "date": "2026-07-08"}
    result = garmin.enrich_session(Boom(), session)
    assert result == {"type": "strength", "date": "2026-07-08"}


class FakeWeighInG:
    def __init__(self):
        self.calls = []

    def add_weigh_in(self, weight, unitKey="kg", timestamp=""):
        self.calls.append({"weight": weight, "unitKey": unitKey, "timestamp": timestamp})
        return {"value": weight, "unitKey": unitKey}


class BoomWeighInG:
    def add_weigh_in(self, weight, unitKey="kg", timestamp=""):
        raise RuntimeError("garmin down")


def test_log_weight_calls_add_weigh_in_with_kg():
    fake = FakeWeighInG()
    result = garmin.log_weight(fake, 69.2)
    assert result == {"ok": True, "kg": 69.2}
    assert fake.calls == [{"weight": 69.2, "unitKey": "kg", "timestamp": ""}]


def test_log_weight_never_raises_on_failure():
    result = garmin.log_weight(BoomWeighInG(), 69.2)
    assert result == {"ok": False, "error": "garmin down"}


def test_build_workout_shape():
    w = garmin.build_workout("Leg day", "strength", "squat 4x5")
    assert w["workoutName"] == "Leg day"
    assert w["description"] == "squat 4x5"
    assert w["sportType"]["sportTypeKey"] == "strength_training"
    assert len(w["workoutSegments"]) == 1
    steps = w["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == 1
    step = steps[0]
    assert step["type"] == "ExecutableStepDTO"
    assert step["endCondition"]["conditionTypeKey"] == "lap.button"
    assert step["targetType"]["workoutTargetTypeKey"] == "no.target"


class FakeWorkoutG:
    def __init__(self):
        self.calls = []

    def upload_workout(self, workout_json):
        self.calls.append(workout_json)
        return {"workoutId": 12345}


class BoomWorkoutG:
    def upload_workout(self, workout_json):
        raise RuntimeError("garmin down")


def test_push_workout_ok():
    fake = FakeWorkoutG()
    result = garmin.push_workout(fake, "Leg day", "strength", "squat 4x5")
    assert result == {"ok": True, "workout_id": 12345}
    assert fake.calls[0]["workoutName"] == "Leg day"


def test_push_workout_never_raises_on_failure():
    result = garmin.push_workout(BoomWorkoutG(), "Leg day", "strength", "squat 4x5")
    assert result["ok"] is False
    assert "garmin down" in result["error"]
