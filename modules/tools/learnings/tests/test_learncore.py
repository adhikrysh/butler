from learncore import (normalize, importance_rank, find_dup, filter_pending,
                       apply_review, format_digest)


def test_normalize():
    assert normalize("  LinkedIn   Snippet ") == "linkedin snippet"
    assert normalize(None) == ""


def test_importance_rank_orders_and_defaults():
    assert importance_rank("high") > importance_rank("med") > importance_rank("low")
    assert importance_rank("bogus") == -1


def test_find_dup_matches_any_status_case_insensitively():
    recs = [{"id": "L-1", "skill": "ppl-index",
             "insight": "Check LinkedIn snippets", "status": "dismissed"}]
    # same lesson, different case/spacing, even though the prior one was dismissed
    assert find_dup(recs, "ppl-index", "check   linkedin snippets")["id"] == "L-1"
    assert find_dup(recs, "ppl-index", "something else") is None


def test_filter_pending_floor_and_order():
    recs = [
        {"id": "L-lo", "importance": "low", "status": "new", "ts": "2026-01-01T00:00:00Z"},
        {"id": "L-hi", "importance": "high", "status": "new", "ts": "2026-01-02T00:00:00Z"},
        {"id": "L-me", "importance": "med", "status": "new", "ts": "2026-01-03T00:00:00Z"},
        {"id": "L-done", "importance": "high", "status": "promoted", "ts": "2026-01-04T00:00:00Z"},
    ]
    assert [r["id"] for r in filter_pending(recs)] == ["L-hi", "L-me"]          # floor med
    assert [r["id"] for r in filter_pending(recs, "low")] == ["L-hi", "L-me", "L-lo"]


def test_apply_review_sets_status_and_reports_found():
    recs = [{"id": "L-1", "status": "new"}, {"id": "L-2", "status": "new"}]
    out, found = apply_review(recs, "L-2", "promoted")
    assert found is True
    assert {r["id"]: r["status"] for r in out} == {"L-1": "new", "L-2": "promoted"}
    _, missing = apply_review(recs, "L-9", "dismissed")
    assert missing is False


def test_format_digest_empty_is_blank():
    assert format_digest([]) == ""


def test_format_digest_groups_labels_and_cta():
    pending = [
        {"id": "L-hi", "skill": "ppl-index", "insight": "snippets first",
         "why": "cheaper", "importance": "high"},
        {"id": "L-me", "skill": "superforecasting", "insight": "normalize casual calls",
         "why": "", "importance": "med"},
    ]
    text = format_digest(pending)
    assert "HIGH" in text and "MED" in text
    assert "[L-hi] ppl-index — snippets first" in text
    assert "why: cheaper" in text
    assert "promoted L-" in text          # the call-to-action line
