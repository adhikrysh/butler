# modules/tools/jim/scripts/jimcore.py
"""jim coach logic — pure functions (no I/O, no gspread, no network)."""
from datetime import date, datetime, timedelta

SESSION_TYPES = {"strength", "run", "ride", "swim", "mobility", "sport", "other"}
CARDIO_TYPES = {"run", "ride", "swim"}
_DIST_BUCKETS = [(1, "1k"), (5, "5k"), (10, "10k"), (21.0975, "half"), (42.195, "full")]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def e1rm(weight, reps) -> float:
    """Estimated 1-rep-max (Epley). A single rep IS the 1RM; Epley only for reps>1."""
    r = int(reps)
    w = float(weight)
    return w if r <= 1 else round(w * (1 + r / 30), 1)


def exercise_metrics(sets: list[dict]) -> dict:
    """top_weight, best_e1rm, total volume, set count for one exercise's sets."""
    ws = [(_f(s.get("weight")), s.get("reps")) for s in sets]
    valid = [(w, int(r)) for w, r in ws if w is not None and r not in (None, "")]
    top = max((w for w, _ in valid), default=None)
    e1s = [e1rm(w, r) for w, r in valid]
    vol = sum(w * r for w, r in valid)
    return {"n_sets": len(sets), "top_weight": top,
            "best_e1rm": max(e1s) if e1s else None, "volume": round(vol, 1)}


def session_volume(exercises: list[dict]) -> float:
    return round(sum(exercise_metrics(e.get("sets", []))["volume"] for e in exercises), 1)


def compute_prs(set_records: list[dict]) -> dict:
    """Best e1RM per exercise from flat set-records ({exercise,e1rm,weight,reps,date})."""
    prs = {}
    for r in set_records:
        ex = str(r.get("exercise", "")).strip().lower()
        v = r.get("e1rm")
        if not ex or v is None:
            continue
        if ex not in prs or v > prs[ex]["e1rm"]:
            prs[ex] = {"e1rm": v, "weight": r.get("weight"), "reps": r.get("reps"),
                       "date": r.get("date")}
    return prs


def progression(set_records: list[dict], exercise: str) -> list[dict]:
    """Best e1RM per day for one exercise, oldest→newest."""
    ex = exercise.strip().lower()
    by = {}
    for r in set_records:
        if str(r.get("exercise", "")).strip().lower() != ex:
            continue
        v = r.get("e1rm")
        if v is None:
            continue
        d = str(r.get("date", ""))[:10]
        if d not in by or v > by[d]["best_e1rm"]:
            by[d] = {"date": d, "best_e1rm": v, "top_weight": r.get("weight")}
    return [by[d] for d in sorted(by)]


def weekly_adherence(sessions: list[dict], programme: dict, today: date) -> dict:
    """Sessions logged this week (Mon–Sun) vs the programme's target frequency."""
    monday = today - timedelta(days=today.weekday())
    done = 0
    for s in sessions:
        try:
            d = date.fromisoformat(str(s.get("date", ""))[:10])
        except ValueError:
            continue
        if monday <= d <= monday + timedelta(days=6):
            done += 1
    target = int((programme or {}).get("freq_per_week") or 0)
    return {"done": done, "target": target, "week_of": monday.isoformat()}


def _fmt(n):
    n = _f(n)
    if n is None:
        return ""
    return str(int(n)) if float(n).is_integer() else str(n)


def render_summary(session: dict, exercises: list[dict]) -> str:
    """Readable one-line summary for the Sheet Sessions row."""
    if session.get("type") in CARDIO_TYPES:
        parts = []
        if session.get("distance_km"):
            parts.append(f"{_fmt(session['distance_km'])}km")
        if session.get("duration_min"):
            parts.append(f"{_fmt(session['duration_min'])}min")
        if session.get("avg_hr"):
            parts.append(f"avg {_fmt(session['avg_hr'])}bpm")
        return " · ".join(parts) or (session.get("feel") or "")
    chunks = []
    for e in exercises:
        sets = ",".join(f"{_fmt(s.get('weight'))}×{s.get('reps')}" for s in e.get("sets", []))
        chunks.append(f"{e.get('exercise', '')} {sets}".strip())
    return " · ".join(chunks)


def render_plan_text(plan: dict) -> str:
    """Readable one-cell render of the structured programme."""
    days = []
    for d in (plan or {}).get("days", []):
        exs = "; ".join(
            f"{e.get('exercise', '')} {e.get('sets', '')}×{e.get('reps', '')}"
            + (f" @{e['load']}" if e.get("load") else "")
            for e in d.get("exercises", []))
        days.append(f"{d.get('day', '')}/{d.get('focus', '')}: {exs}")
    freq = plan.get("freq_per_week")
    tail = f" | {freq}×/wk" if freq else ""
    return " | ".join(days) + tail


def latest_active(programme_rows: list[dict]) -> dict | None:
    act = [r for r in programme_rows if str(r.get("active", "")) in ("1", "True", "true")]
    return max(act, key=lambda r: str(r.get("date", "")), default=None)


def active_goals(goal_rows: list[dict]) -> list[dict]:
    return [g for g in goal_rows if str(g.get("status", "active")).lower() == "active"]
