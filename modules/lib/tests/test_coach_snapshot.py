import garmin


class FakeG:
    def get_race_predictions(self): return {"time5K":1500,"time10K":3200,"timeHalfMarathon":7000,"timeMarathon":15000,"calendarDate":"2026-07-08"}
    def get_training_status(self, d): return {"mostRecentVO2Max":{"generic":{"vo2MaxPreciseValue":52.3}},
        "mostRecentTrainingLoadBalance":{"metricsTrainingLoadBalanceDTOMap":{"x":{"trainingBalanceFeedbackPhrase":"BALANCED"}}},
        "mostRecentTrainingStatus":{"latestTrainingStatusData":{"dev1":{"trainingStatusFeedbackPhrase":"PRODUCTIVE_1"}}}}
    def get_weigh_ins(self, s, e): return {"totalAverage":{"weight":68500.0}, "dailyWeightSummaries":[{"summaryDate":"2026-07-08"}]}
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
    assert w["latest_kg"] == 68.5


def test_garmin_prs():
    p = garmin.garmin_prs(FakeG())
    assert p[0]["label"] == "PR_5K" and p[0]["value"] == 1490


def test_coach_snapshot_groups_and_never_raises():
    class Boom:
        def __getattr__(self, n):
            def f(*a, **k): raise RuntimeError("garmin down")
            return f
    snap = garmin.coach_snapshot(Boom(), "2026-07-08")
    assert set(snap.keys()) == {"recovery","fitness","body"}   # degrades, doesn't raise
