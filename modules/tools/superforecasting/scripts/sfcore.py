"""Superforecasting core logic — pure functions (no I/O, no gspread)."""
import re
from datetime import date, timedelta


def parse_window(s, default_days: int = 90) -> int:
    """Parse a review window into days. '3 months'->90, '6 weeks'->42,
    '1 year'->365, '45'->45, ''/None->default. Months ~30d, years ~365d."""
    s = str(s or "").strip().lower()
    if not s:
        return default_days
    m = re.fullmatch(r"(\d+)\s*([a-z]*)", s)
    if not m:
        return default_days
    n = int(m.group(1))
    unit = m.group(2) or "d"
    if unit[0] == "w":
        return n * 7
    if unit[0] == "y":
        return n * 365
    if unit[0] == "m":   # months in this domain (not minutes)
        return n * 30
    return n             # days (incl. bare numbers)


def compute_review_date(decided: date, window_days: int) -> date:
    return decided + timedelta(days=window_days)


def parse_confidence(s) -> int | None:
    """'70%'/'70'/'0.7' -> 70 (int 0..100); unparseable/blank -> None."""
    s = str(s or "").strip().replace("%", "")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if 0 <= v <= 1:
        v *= 100
    v = int(round(v))
    return v if 0 <= v <= 100 else None


def is_open(row: dict) -> bool:
    return str(row.get("status", "")).strip().lower() not in ("reviewed", "dropped", "resolved", "closed")


def select_due(rows: list[dict], today: date) -> list[dict]:
    """Open decisions whose review_date has arrived (parseable, <= today)."""
    due = []
    for r in rows:
        if not is_open(r):
            continue
        raw = str(r.get("review_date", "")).strip()
        if not raw:
            continue
        try:
            rd = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        if rd <= today:
            due.append(r)
    return due


def _verdict_score(v) -> float | None:
    v = str(v or "").strip().lower()
    if v.startswith(("right", "correct", "yes", "hit", "true", "win")):
        return 1.0
    if v.startswith(("wrong", "incorrect", "no", "miss", "false", "loss", "lose")):
        return 0.0
    if v.startswith(("mixed", "partial", "half")):
        return 0.5
    return None


def calibration(rows: list[dict], bucket: int = 10) -> list[dict]:
    """Hit-rate by confidence bucket over reviewed rows with a scorable verdict.
    Returns [{bucket, n, predicted, actual}] sorted by bucket. Calibration is
    good when predicted ≈ actual; predicted>actual = overconfident."""
    agg: dict[int, dict] = {}
    for r in rows:
        c = parse_confidence(r.get("confidence"))
        s = _verdict_score(r.get("verdict"))
        if c is None or s is None:
            continue
        b = int(round(c / bucket) * bucket)
        d = agg.setdefault(b, {"n": 0, "pred_sum": 0, "hit_sum": 0.0})
        d["n"] += 1
        d["pred_sum"] += c
        d["hit_sum"] += s
    return [{"bucket": b, "n": agg[b]["n"],
             "predicted": round(agg[b]["pred_sum"] / agg[b]["n"]),
             "actual": round(100 * agg[b]["hit_sum"] / agg[b]["n"])}
            for b in sorted(agg)]
