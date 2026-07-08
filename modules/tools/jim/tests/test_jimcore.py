# modules/tools/jim/tests/test_jimcore.py
from datetime import date, timedelta
from jimcore import (e1rm, exercise_metrics, session_volume, compute_prs, progression,
                     weekly_adherence, render_summary, render_plan_text,
                     latest_active, active_goals, SESSION_TYPES, CARDIO_TYPES,
                     training_age, weekly_muscle_volume, progression_stalled,
                     easy_run_too_hard, deload_due, MUSCLE_MAP, READINESS_DELOAD_THRESHOLD)


def test_e1rm():
    assert e1rm(100, 1) == 100.0
    assert round(e1rm(100, 5), 1) == 116.7


def test_exercise_metrics():
    m = exercise_metrics([{"weight": 80, "reps": 8}, {"weight": 100, "reps": 8},
                          {"weight": 120, "reps": 8}, {"weight": 140, "reps": 8}])
    assert m["n_sets"] == 4
    assert m["top_weight"] == 140.0
    assert m["best_e1rm"] == e1rm(140, 8)
    assert m["volume"] == round(80*8 + 100*8 + 120*8 + 140*8, 1)


def test_session_volume():
    ex = [{"exercise": "squat", "sets": [{"weight": 100, "reps": 5}]},
          {"exercise": "bench", "sets": [{"weight": 60, "reps": 10}]}]
    assert session_volume(ex) == round(100*5 + 60*10, 1)


SET_RECORDS = [
    {"exercise": "leg extension", "weight": 100, "reps": 8, "e1rm": 126.7, "date": "2026-07-01T18:00"},
    {"exercise": "leg extension", "weight": 140, "reps": 8, "e1rm": 177.3, "date": "2026-07-07T18:00"},
    {"exercise": "bench", "weight": 80, "reps": 5, "e1rm": 93.3, "date": "2026-07-03T18:00"},
]


def test_compute_prs():
    prs = compute_prs(SET_RECORDS)
    assert prs["leg extension"]["e1rm"] == 177.3
    assert prs["bench"]["e1rm"] == 93.3


def test_progression_orders_by_date():
    p = progression(SET_RECORDS, "leg extension")
    assert [x["date"] for x in p] == ["2026-07-01", "2026-07-07"]
    assert p[-1]["best_e1rm"] == 177.3


def test_weekly_adherence_counts_sessions_vs_freq():
    sessions = [{"date": "2026-07-06T18:00", "type": "strength"},   # Mon
                {"date": "2026-07-08T18:00", "type": "run"}]         # Wed
    plan = {"freq_per_week": 5, "days": []}
    a = weekly_adherence(sessions, plan, date(2026, 7, 8))          # week Mon 7/6..Sun 7/12
    assert a["done"] == 2 and a["target"] == 5


def test_render_summary_strength_and_cardio():
    s = render_summary({"type": "strength"},
                       [{"exercise": "leg ext", "sets": [{"weight": 80, "reps": 8}, {"weight": 100, "reps": 8}]}])
    assert s == "leg ext 80×8,100×8"
    c = render_summary({"type": "run", "distance_km": 10.2, "duration_min": 52, "avg_hr": 145}, [])
    assert c == "10.2km · 52min · avg 145bpm"


def test_render_plan_text():
    plan = {"freq_per_week": 5, "days": [
        {"day": "A", "focus": "legs", "exercises": [{"exercise": "squat", "sets": 4, "reps": 5, "load": "RPE8"},
                                                    {"exercise": "leg ext", "sets": 4, "reps": 8}]}]}
    t = render_plan_text(plan)
    assert "A/legs" in t and "squat 4×5 @RPE8" in t and "5×/wk" in t


def test_latest_active_and_active_goals():
    progs = [{"id": 1, "date": "2026-06-01", "active": 0, "name": "old"},
             {"id": 2, "date": "2026-07-01", "active": 1, "name": "current"}]
    assert latest_active(progs)["name"] == "current"
    goals = [{"metric": "bodyweight", "status": "active"}, {"metric": "bench", "status": "hit"}]
    assert [g["metric"] for g in active_goals(goals)] == ["bodyweight"]


def test_type_constants():
    assert CARDIO_TYPES <= SESSION_TYPES


def test_exercise_metrics_survives_bad_reps():
    m = exercise_metrics([{"weight": 100, "reps": "8-10"}, {"weight": 80, "reps": 5}])
    assert m["top_weight"] == 80.0 and m["best_e1rm"] == e1rm(80, 5)  # bad set skipped, no crash


def test_compute_cardio_prs():
    from jimcore import compute_cardio_prs
    prs = compute_cardio_prs([
        {"type": "run", "distance_km": 10.2, "duration_min": 52, "date": "2026-07-11T07:00"},
        {"type": "run", "distance_km": 5.0, "duration_min": 27, "date": "2026-07-12T07:00"},
        {"type": "strength", "distance_km": None, "duration_min": None, "date": "2026-07-13"}])
    assert prs["10k"]["pace_min_per_km"] == round(52 / 10.2, 2)
    assert prs["5k"]["pace_min_per_km"] == round(27 / 5.0, 2)


# ---- Task 6: training-age + autoregulation helpers ----

def _weeks(n, start="2026-01-05"):  # start on a Monday
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(weeks=i)).isoformat() for i in range(n)]


_MODERATE_DATES = _weeks(8)  # 8 distinct training weeks: below the intermediate week threshold
_MODERATE_SESSIONS = [{"date": d, "type": "strength"} for d in _MODERATE_DATES]

# Squat is the most-logged lift (6 records) and its last 3 e1RM points are non-increasing.
_STALLED_SQUAT = [
    {"exercise": "squat", "e1rm": 150, "date": _MODERATE_DATES[0]},
    {"exercise": "squat", "e1rm": 150, "date": _MODERATE_DATES[1]},
    {"exercise": "squat", "e1rm": 160, "date": _MODERATE_DATES[2]},
    {"exercise": "squat", "e1rm": 155, "date": _MODERATE_DATES[5]},
    {"exercise": "squat", "e1rm": 150, "date": _MODERATE_DATES[6]},
    {"exercise": "squat", "e1rm": 145, "date": _MODERATE_DATES[7]},
]

# Same lift, same schedule, but still climbing every time it's tested.
_PROGRESSING_SQUAT = [
    {"exercise": "squat", "e1rm": 100, "date": _MODERATE_DATES[0]},
    {"exercise": "squat", "e1rm": 110, "date": _MODERATE_DATES[1]},
    {"exercise": "squat", "e1rm": 120, "date": _MODERATE_DATES[2]},
    {"exercise": "squat", "e1rm": 140, "date": _MODERATE_DATES[5]},
    {"exercise": "squat", "e1rm": 150, "date": _MODERATE_DATES[6]},
    {"exercise": "squat", "e1rm": 160, "date": _MODERATE_DATES[7]},
]


def test_training_age_empty_is_novice():
    assert training_age([], []) == "novice"


def test_training_age_novice_when_still_progressing():
    assert training_age(_MODERATE_SESSIONS, _PROGRESSING_SQUAT) == "novice"


def test_training_age_stalled_top_lift_flips_to_intermediate():
    assert training_age(_MODERATE_SESSIONS, _STALLED_SQUAT) == "intermediate"


def test_training_age_long_history_is_advanced():
    sessions = [{"date": "2020-01-06", "type": "strength"}, {"date": "2026-07-01", "type": "strength"}]
    assert training_age(sessions, []) == "advanced"


def test_weekly_muscle_volume_rolls_up_quads():
    records = [
        {"exercise": "leg extension", "date": "2026-07-06T18:00"},
        {"exercise": "leg extension", "date": "2026-07-07T18:00"},
        {"exercise": "squat", "date": "2026-07-08T18:00"},
        {"exercise": "bench", "date": "2026-07-08T18:00"},
        {"exercise": "leg extension", "date": "2026-06-29T18:00"},  # prior week, excluded
    ]
    vol = weekly_muscle_volume(records, date(2026, 7, 8))
    assert vol["quads"] == 3
    assert vol["chest"] == 1
    assert "quads" in MUSCLE_MAP.values()


_OHP_STALLED = [
    {"exercise": "ohp", "e1rm": 100, "date": "2026-06-01"},
    {"exercise": "ohp", "e1rm": 100, "date": "2026-06-08"},
    {"exercise": "ohp", "e1rm": 90, "date": "2026-06-15"},
]
_OHP_PROGRESSING = [
    {"exercise": "ohp", "e1rm": 100, "date": "2026-06-01"},
    {"exercise": "ohp", "e1rm": 105, "date": "2026-06-08"},
    {"exercise": "ohp", "e1rm": 110, "date": "2026-06-15"},
]


def test_progression_stalled_true_when_non_increasing():
    assert progression_stalled(_OHP_STALLED, "ohp") is True


def test_progression_stalled_false_when_climbing():
    assert progression_stalled(_OHP_PROGRESSING, "ohp") is False


def test_progression_stalled_false_with_too_few_points():
    assert progression_stalled(_OHP_STALLED[:2], "ohp") is False


def test_easy_run_too_hard_true_and_false():
    assert easy_run_too_hard({"type": "run", "avg_hr": 160}, 150) is True
    assert easy_run_too_hard({"type": "run", "avg_hr": 140}, 150) is False
    assert easy_run_too_hard({"type": "strength", "avg_hr": 200}, 150) is False
    assert easy_run_too_hard({"type": "run"}, 150) is False


def test_deload_due_on_low_readiness_or_hrv():
    assert deload_due([], {"readiness_score": 40, "hrv_status": "BALANCED"}) is True
    assert deload_due([], {"readiness_score": 70, "hrv_status": "UNBALANCED"}) is True
    assert deload_due([], {"readiness_score": 70, "hrv_status": "BALANCED"}) is False
    assert deload_due([], {}) is False
    assert deload_due([], None) is False


# ---- Task 6 review follow-up: close coverage gaps on already-correct branches ----

# 30 distinct Mon-Sun weeks: >= INTERMEDIATE_WEEKS_THRESHOLD (24) but far short of the
# ADVANCED_WEEKS_THRESHOLD (104) week-span cutoff.
_FREQ_ONLY_DATES = _weeks(30)
_FREQ_ONLY_SESSIONS = [{"date": d, "type": "strength"} for d in _FREQ_ONLY_DATES]
# Squat weight climbs every week, so e1RM (via the real e1rm()) is strictly increasing ->
# progression_stalled() is False. Any "intermediate" verdict here must come from the
# distinct-weeks branch alone, not the stall branch.
_FREQ_ONLY_PROGRESSING_SQUAT = [
    {"exercise": "squat", "e1rm": e1rm(100 + 5 * i, 5), "date": d}
    for i, d in enumerate(_FREQ_ONLY_DATES)
]


def test_training_age_intermediate_via_frequency_alone_no_stall():
    assert progression_stalled(_FREQ_ONLY_PROGRESSING_SQUAT, "squat") is False
    assert training_age(_FREQ_ONLY_SESSIONS, _FREQ_ONLY_PROGRESSING_SQUAT) == "intermediate"


def test_weekly_muscle_volume_buckets_unmapped_exercise_as_other():
    assert "face pull" not in MUSCLE_MAP  # confirm it's genuinely unmapped
    records = [
        {"exercise": "face pull", "date": "2026-07-06T18:00"},
        {"exercise": "face pull", "date": "2026-07-07T18:00"},
        {"exercise": "squat", "date": "2026-07-08T18:00"},
    ]
    vol = weekly_muscle_volume(records, date(2026, 7, 8))
    assert vol["other"] == 2
    assert vol["quads"] == 1


def test_deload_due_readiness_boundary():
    # Exactly at the threshold is NOT due (strict "<" in the implementation); one point
    # below IS due; one point above is not. Guards against a future "<" -> "<=" flip.
    assert deload_due([], {"readiness_score": READINESS_DELOAD_THRESHOLD}) is False
    assert deload_due([], {"readiness_score": READINESS_DELOAD_THRESHOLD - 1}) is True
    assert deload_due([], {"readiness_score": READINESS_DELOAD_THRESHOLD + 1}) is False
