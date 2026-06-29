from datetime import date

from outboundcore import select_nudges, is_bulk, derive_status, counterpart, build_threads, initiated

ROWS = [
    {"name": "Alex",    "replied": "no reply", "status": "active",  "sent_date": "2026-05-28"},
    {"name": "Mira", "replied": "replied",  "status": "active",  "sent_date": "2026-06-20"},
    {"name": "Gone",   "replied": "no reply", "status": "dropped", "sent_date": "2026-05-01"},
    {"name": "Fresh",  "replied": "no reply", "status": "active",  "sent_date": "2026-06-20"},
    {"name": "NoDate", "replied": "no reply", "status": "active",  "sent_date": ""},
]


def test_only_cold_unreplied_active():
    assert [r["name"] for r in select_nudges(ROWS, date(2026, 6, 22), cold_days=7)] == ["Alex"]


def test_snoozed_excluded():
    rows = [{"name": "S", "replied": "no reply", "status": "snoozed", "sent_date": "2026-01-01"}]
    assert select_nudges(rows, date(2026, 6, 22)) == []


def test_no_sent_date_skipped():
    rows = [{"name": "N", "replied": "no reply", "status": "active", "sent_date": ""}]
    assert select_nudges(rows, date(2026, 6, 22)) == []


def test_replied_excluded():
    rows = [{"name": "R", "replied": "replied", "status": "active", "sent_date": "2026-01-01"}]
    assert select_nudges(rows, date(2026, 6, 22)) == []


def test_is_bulk_list_unsubscribe():
    assert is_bulk({"from_email": "news@co.com", "headers": {"List-Unsubscribe": "<x>"}}) is True


def test_is_bulk_noreply_sender():
    assert is_bulk({"from_email": "no-reply@svc.com", "headers": {}}) is True


def test_is_bulk_human_false():
    assert is_bulk({"from_email": "jane@example.com", "headers": {}}) is False


def test_derive_status_replied():
    t = {"last_outbound": date(2026, 6, 1), "last_inbound": date(2026, 6, 3)}
    assert derive_status(t, date(2026, 6, 22))["status"] == "replied"


def test_derive_status_cold():
    t = {"last_outbound": date(2026, 6, 1), "last_inbound": None}
    r = derive_status(t, date(2026, 6, 22), cold_days=7)
    assert r["status"] == "cold" and r["days_since"] == 21


def test_derive_status_awaiting_recent():
    t = {"last_outbound": date(2026, 6, 20), "last_inbound": None}
    assert derive_status(t, date(2026, 6, 22), cold_days=7)["status"] == "awaiting"


def test_counterpart_outbound_is_recipient():
    m = {"direction": "outbound", "to_emails": ["me@example.com", "jane@example.com"], "from_email": "me@example.com"}
    assert counterpart(m, {"me@example.com"}) == "jane@example.com"


def test_counterpart_inbound_is_sender():
    m = {"direction": "inbound", "from_email": "bob@co.com", "to_emails": ["me@example.com"]}
    assert counterpart(m, {"me@example.com"}) == "bob@co.com"


def test_counterpart_none_when_only_self():
    m = {"direction": "outbound", "to_emails": ["me@example.com"], "from_email": "me@example.com"}
    assert counterpart(m, {"me@example.com"}) == ""


def test_build_threads_aggregates_and_keeps_latest_outbound_subject():
    msgs = [
        {"direction": "outbound", "to_emails": ["jane@example.com"], "from_email": "me@example.com",
         "date_utc": "2026-05-28T10:00:00+00:00", "subject": "old", "account": "gmail"},
        {"direction": "outbound", "to_emails": ["jane@example.com"], "from_email": "me@example.com",
         "date_utc": "2026-06-01T10:00:00+00:00", "subject": "newer", "account": "gmail"},
        {"direction": "inbound", "from_email": "jane@example.com", "to_emails": ["me@example.com"],
         "date_utc": "2026-06-03T10:00:00+00:00", "subject": "re", "account": "gmail"},
    ]
    th = build_threads(msgs, {"me@example.com"})
    j = th["jane@example.com"]
    assert j["last_outbound"] == date(2026, 6, 1)
    assert j["last_inbound"] == date(2026, 6, 3)
    assert j["n_out"] == 2 and j["n_in"] == 1
    assert j["subject"] == "newer"


def test_initiated_skips_replies_and_forwards():
    assert initiated("Intro: Sam <> Jane") is True
    assert initiated("Re: Quick question") is False
    assert initiated("Fwd: Your Flight Confirmation") is False
    assert initiated("") is False
