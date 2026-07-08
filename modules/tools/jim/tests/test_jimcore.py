# modules/tools/jim/tests/test_jimcore.py
from datetime import date
from jimcore import (e1rm, exercise_metrics, session_volume, compute_prs, progression,
                     weekly_adherence, render_summary, render_plan_text,
                     latest_active, active_goals, SESSION_TYPES, CARDIO_TYPES)


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
