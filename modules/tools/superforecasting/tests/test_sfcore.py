from datetime import date

from sfcore import (parse_window, parse_confidence, compute_review_date,
                   select_due, calibration)


def test_parse_window():
    assert parse_window("3 months") == 90
    assert parse_window("6 weeks") == 42
    assert parse_window("1 year") == 365
    assert parse_window("45") == 45
    assert parse_window("45 days") == 45
    assert parse_window("") == 90
    assert parse_window(None) == 90


def test_parse_confidence():
    assert parse_confidence("70%") == 70
    assert parse_confidence("70") == 70
    assert parse_confidence("0.7") == 70
    assert parse_confidence("") is None
    assert parse_confidence("high") is None
    assert parse_confidence("150%") is None


def test_compute_review_date():
    assert compute_review_date(date(2026, 1, 1), 90) == date(2026, 4, 1)


DUE_ROWS = [
    {"decision": "A", "review_date": "2026-06-01", "status": "open"},
    {"decision": "B", "review_date": "2026-07-01", "status": "open"},      # future
    {"decision": "C", "review_date": "2026-05-01", "status": "reviewed"},  # done
    {"decision": "D", "review_date": "", "status": "open"},                # no date
]


def test_select_due():
    assert [r["decision"] for r in select_due(DUE_ROWS, date(2026, 6, 15))] == ["A"]


def test_calibration_buckets_and_hit_rate():
    rows = [
        {"confidence": "70%", "verdict": "right"},
        {"confidence": "72%", "verdict": "wrong"},
        {"confidence": "90%", "verdict": "right"},
        {"confidence": "bad", "verdict": "right"},   # unparseable conf -> skipped
        {"confidence": "50%", "verdict": ""},        # no verdict -> skipped
    ]
    cal = {c["bucket"]: c for c in calibration(rows)}
    assert cal[70]["n"] == 2
    assert cal[70]["actual"] == 50      # 1 of 2 right
    assert cal[70]["predicted"] == 71   # avg(70, 72)
    assert cal[90]["n"] == 1 and cal[90]["actual"] == 100
    assert 50 not in cal                # the no-verdict row produced no bucket
