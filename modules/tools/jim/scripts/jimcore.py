# modules/tools/jim/scripts/jimcore.py
"""jim coach logic — pure functions (no I/O, no gspread, no network)."""
import re

SESSION_TYPES = {"strength", "run", "ride", "swim", "mobility", "sport", "other"}
META_TYPES = {"goal", "plan", "note"}

# the numeric core of a set: "5x5@100", "3 x 8 @ 80", unicode ×, optional decimal
_CORE_RE = re.compile(r"(\d+)\s*[x×]\s*(\d+)\s*@\s*(\d+(?:\.\d+)?)")
_WORD_RE = re.compile(r"[A-Za-z'\-]+")

# nearest-standard distance buckets (km) with ±8% tolerance
_DIST_BUCKETS = [(1, "1k"), (5, "5k"), (10, "10k"), (21.0975, "half"), (42.195, "full")]


def parse_strength(remarks: str) -> list[dict]:
    """Parse a strength remarks line into structured sets. Linear-time: scan for
    each NxR@weight core, then take the trailing alphabetic words immediately
    before it as the exercise name. Avoids regex backtracking on long free-text
    remarks (a lazy name group that overlaps the following whitespace is O(n²))."""
    out = []
    text = remarks or ""
    prev_end = 0
    for m in _CORE_RE.finditer(text):
        words = text[prev_end:m.start()].split()
        prev_end = m.end()
        name = []
        for w in reversed(words):          # collect trailing alpha words as the name
            if _WORD_RE.fullmatch(w):
                name.insert(0, w)
            else:
                break
        if not name:
            continue
        out.append({
            "exercise": " ".join(name).lower(),
            "sets": int(m.group(1)),
            "reps": int(m.group(2)),
            "weight": float(m.group(3)),
        })
    return out


def e1rm(weight: float, reps: int) -> float:
    """Estimated 1-rep-max (Epley). A single rep IS the 1RM; Epley only applies
    for reps > 1 (at reps=1 the raw formula would inflate by 1/30)."""
    reps = int(reps)
    if reps <= 1:
        return float(weight)
    return float(weight) * (1 + reps / 30)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pace_bucket(dist_km: float):
    for std, label in _DIST_BUCKETS:
        if abs(dist_km - std) <= std * 0.08 + 1e-9:   # epsilon: float-safe boundary
            return label
    return None


def compute_prs(rows: list[dict]) -> dict:
    """Best e1RM per lift + best pace per distance bucket, from the log."""
    strength, cardio = {}, {}
    for r in rows:
        t = str(r.get("type", "")).lower()
        if t == "strength":
            for s in parse_strength(r.get("remarks", "")):
                val = round(e1rm(s["weight"], s["reps"]), 1)
                cur = strength.get(s["exercise"])
                if cur is None or val > cur["e1rm"]:
                    strength[s["exercise"]] = {
                        "e1rm": val, "weight": s["weight"], "reps": s["reps"],
                        "date": r.get("datetime")}
        elif t in ("run", "ride", "swim"):
            dist, dur = _f(r.get("distance_km")), _f(r.get("duration_min"))
            if dist and dur and dist > 0:
                bucket = _pace_bucket(dist)
                if not bucket:
                    continue
                pace = round(dur / dist, 2)
                cur = cardio.get(bucket)
                if cur is None or pace < cur["pace_min_km"]:
                    cardio[bucket] = {"pace_min_km": pace, "distance_km": dist,
                                      "date": r.get("datetime")}
    return {"strength": strength, "cardio": cardio}


def _by_dt(rows):
    return sorted(rows, key=lambda r: str(r.get("datetime", "")))


def latest_by_type(rows: list[dict], type_: str) -> dict | None:
    matches = [r for r in rows if str(r.get("type", "")).lower() == type_]
    return _by_dt(matches)[-1] if matches else None


def latest_goals(rows: list[dict]) -> list[dict]:
    """All goal rows, newest first."""
    goals = [r for r in rows if str(r.get("type", "")).lower() == "goal"]
    return list(reversed(_by_dt(goals)))


def recent_sessions(rows: list[dict], n: int) -> list[dict]:
    """Last n session (non-meta) rows, newest first."""
    sessions = [r for r in rows if str(r.get("type", "")).lower() in SESSION_TYPES]
    return list(reversed(_by_dt(sessions)))[:n]
