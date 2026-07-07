# modules/tools/jim/tests/test_jimcore.py
from jimcore import (parse_strength, e1rm, compute_prs, latest_by_type,
                     latest_goals, recent_sessions, SESSION_TYPES, META_TYPES)


def test_parse_strength():
    sets = parse_strength("Squat 5x5@100; Bench 3x8@80kg")
    assert sets == [
        {"exercise": "squat", "sets": 5, "reps": 5, "weight": 100.0},
        {"exercise": "bench", "sets": 3, "reps": 8, "weight": 80.0},
    ]
    assert parse_strength("") == []
    assert parse_strength("felt good, no numbers") == []


def test_parse_strength_multiword_and_unicode():
    assert parse_strength("Front Squat 5 x 3 @ 90") == [
        {"exercise": "front squat", "sets": 5, "reps": 3, "weight": 90.0}]
    assert parse_strength("Squat 5×5@100") == [
        {"exercise": "squat", "sets": 5, "reps": 5, "weight": 100.0}]


def test_parse_strength_long_freetext_is_empty_not_slow():
    assert parse_strength("word " * 5000) == []   # no core pattern -> [], linear time


def test_pace_bucket_boundary():
    from jimcore import _pace_bucket
    assert _pace_bucket(4.6) == "5k"     # float-safe lower edge of ±8%
    assert _pace_bucket(5.4) == "5k"     # upper edge
    assert _pace_bucket(7.0) is None     # between 5k and 10k


def test_e1rm_epley():
    assert round(e1rm(100, 5), 1) == 116.7      # 100*(1+5/30)
    assert e1rm(100, 1) == 100.0


ROWS = [
    {"datetime": "2026-07-01T18:00", "type": "strength", "remarks": "Squat 5x5@100"},
    {"datetime": "2026-07-03T18:00", "type": "strength", "remarks": "Squat 3x3@110"},
    {"datetime": "2026-07-02T07:00", "type": "run", "distance_km": "10", "duration_min": "50"},
    {"datetime": "2026-07-05T07:00", "type": "run", "distance_km": "10", "duration_min": "45"},
    {"datetime": "2026-06-20T09:00", "type": "goal", "title": "Bodyweight 78kg", "remarks": "target 78kg by Oct"},
    {"datetime": "2026-07-04T09:00", "type": "plan", "title": "Block A", "remarks": "4-week base: 3 lifts + 2 easy runs / wk"},
    {"datetime": "2026-07-06T09:00", "type": "plan", "title": "Block B", "remarks": "deload week"},
]


def test_compute_prs_strength_best_e1rm():
    prs = compute_prs(ROWS)
    # 3x3@110 -> e1rm 121 beats 5x5@100 -> e1rm 116.7
    assert prs["strength"]["squat"]["e1rm"] == 121.0


def test_compute_prs_cardio_best_pace():
    prs = compute_prs(ROWS)
    # fastest 10k: 45min/10k = 4.5 min/km beats 5.0
    assert prs["cardio"]["10k"]["pace_min_km"] == 4.5


def test_latest_by_type_returns_most_recent():
    assert latest_by_type(ROWS, "plan")["title"] == "Block B"


def test_latest_goals_returns_all_goal_rows_newest_first():
    goals = latest_goals(ROWS)
    assert [g["title"] for g in goals] == ["Bodyweight 78kg"]


def test_recent_sessions_excludes_meta_and_orders_newest_first():
    rs = recent_sessions(ROWS, 2)
    assert all(r["type"] in SESSION_TYPES for r in rs)
    assert rs[0]["datetime"] == "2026-07-05T07:00"


def test_type_constants_disjoint():
    assert not (SESSION_TYPES & META_TYPES)
