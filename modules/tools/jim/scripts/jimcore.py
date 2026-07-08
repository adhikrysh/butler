# modules/tools/jim/scripts/jimcore.py
"""jim coach logic — pure functions (no I/O, no gspread, no network)."""
from datetime import date, datetime, timedelta

SESSION_TYPES = {"strength", "run", "ride", "swim", "mobility", "sport", "other"}
CARDIO_TYPES = {"run", "ride", "swim"}
_DIST_BUCKETS = [(1, "1k"), (5, "5k"), (10, "10k"), (21.0975, "half"), (42.195, "full")]

# Seed exercise -> muscle-group map (lowercased exercise name). Unknown exercises -> "other".
MUSCLE_MAP = {
    "leg extension": "quads",
    "squat": "quads",
    "leg press": "quads",
    "ham curls": "hamstrings",
    "romanian deadlift": "hamstrings",
    "bench": "chest",
    "bench press": "chest",
    "ohp": "shoulders",
    "overhead press": "shoulders",
    "row": "back",
    "pulldown": "back",
    "deadlift": "back",
    "bicep curl": "biceps",
    "tricep": "triceps",
    "calf raise": "calves",
}

# training_age thresholds (deliberately simple heuristics, see training_age()).
ADVANCED_WEEKS_THRESHOLD = 104   # > this many weeks of logged history -> "advanced"
INTERMEDIATE_WEEKS_THRESHOLD = 24  # >= this many distinct training weeks -> "intermediate"
STALL_N = 3  # progression_stalled() default window used by training_age()

# deload_due() thresholds.
READINESS_DELOAD_THRESHOLD = 45
LOW_HRV_STATUSES = {"UNBALANCED", "LOW", "POOR"}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def e1rm(weight, reps) -> float:
    """Estimated 1-rep-max (Epley). A single rep IS the 1RM; Epley only for reps>1."""
    r = int(reps)
    w = float(weight)
    return w if r <= 1 else round(w * (1 + r / 30), 1)


def exercise_metrics(sets: list[dict]) -> dict:
    """top_weight, best_e1rm, total volume, set count for one exercise's sets."""
    pairs = [(_f(s.get("weight")), _int(s.get("reps"))) for s in sets]
    valid = [(w, r) for w, r in pairs if w is not None and r is not None]
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


def progression_stalled(set_records: list[dict], exercise: str, n: int = STALL_N) -> bool:
    """True if the last n per-session best-e1RM points for `exercise` are non-increasing."""
    pts = progression(set_records, exercise)
    if len(pts) < n:
        return False
    vals = [p["best_e1rm"] for p in pts[-n:]]
    return all(vals[i] <= vals[i - 1] for i in range(1, len(vals)))


def _distinct_training_weeks(sessions: list[dict]) -> set:
    weeks = set()
    for s in sessions:
        try:
            d = date.fromisoformat(str(s.get("date", ""))[:10])
        except ValueError:
            continue
        weeks.add(d - timedelta(days=d.weekday()))
    return weeks


def _most_trained_exercise(set_records: list[dict]) -> str | None:
    counts: dict[str, int] = {}
    for r in set_records:
        ex = str(r.get("exercise", "")).strip().lower()
        if not ex:
            continue
        counts[ex] = counts.get(ex, 0) + 1
    return max(counts, key=counts.get, default=None)


def training_age(sessions: list[dict], set_records: list[dict]) -> str:
    """"novice"|"intermediate"|"advanced", from logged history + progression.

    Heuristic (deliberately simple, defaults documented at the constants above):
    - "advanced" if the session history spans > ADVANCED_WEEKS_THRESHOLD weeks.
    - else "intermediate" if there are >= INTERMEDIATE_WEEKS_THRESHOLD distinct
      Mon-Sun training weeks, OR the most-logged lift has stalled (its last
      STALL_N per-session best-e1RM points are non-increasing).
    - else "novice" (also the default for missing/empty input).
    """
    dates = []
    for s in sessions:
        try:
            dates.append(date.fromisoformat(str(s.get("date", ""))[:10]))
        except ValueError:
            continue
    if not dates:
        return "novice"
    span_weeks = (max(dates) - min(dates)).days / 7.0
    if span_weeks > ADVANCED_WEEKS_THRESHOLD:
        return "advanced"
    distinct_weeks = len(_distinct_training_weeks(sessions))
    top_ex = _most_trained_exercise(set_records)
    stalled = bool(top_ex) and progression_stalled(set_records, top_ex, n=STALL_N)
    if distinct_weeks >= INTERMEDIATE_WEEKS_THRESHOLD or stalled:
        return "intermediate"
    return "novice"


def weekly_muscle_volume(set_records: list[dict], week_of: date) -> dict:
    """Hard-set count per muscle group (via MUSCLE_MAP) for the Mon-Sun week containing week_of.

    One `jim_sets` record == one hard set.
    """
    monday = week_of - timedelta(days=week_of.weekday())
    sunday = monday + timedelta(days=6)
    out: dict[str, int] = {}
    for r in set_records:
        try:
            d = date.fromisoformat(str(r.get("date", ""))[:10])
        except ValueError:
            continue
        if not (monday <= d <= sunday):
            continue
        ex = str(r.get("exercise", "")).strip().lower()
        muscle = MUSCLE_MAP.get(ex, "other")
        out[muscle] = out.get(muscle, 0) + 1
    return out


def easy_run_too_hard(session: dict, z2_ceiling_hr) -> bool:
    """True iff a cardio session's avg HR ran above the Z2 ceiling."""
    if (session or {}).get("type") not in CARDIO_TYPES:
        return False
    hr = _f(session.get("avg_hr"))
    ceiling = _f(z2_ceiling_hr)
    if hr is None or ceiling is None:
        return False
    return hr > ceiling


def deload_due(recovery: dict) -> bool:
    """True if recovery signals elevated fatigue (low readiness score or poor HRV status)."""
    if not recovery:
        return False
    score = _f(recovery.get("readiness_score"))
    if score is not None and score < READINESS_DELOAD_THRESHOLD:
        return True
    hrv = str(recovery.get("hrv_status") or "").upper()
    return hrv in LOW_HRV_STATUSES


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


def _pace_bucket(distance_km: float):
    """Largest standard distance this run covers (e.g. 6 km -> '5k'). +epsilon for float edges."""
    for dist, label in reversed(_DIST_BUCKETS):
        if distance_km + 1e-9 >= dist:
            return label
    return None


def compute_cardio_prs(sessions: list[dict]) -> dict:
    """Best (lowest) pace min/km per distance bucket, from cardio sessions with distance+duration."""
    prs = {}
    for s in sessions:
        if s.get("type") not in CARDIO_TYPES:
            continue
        d, t = _f(s.get("distance_km")), _f(s.get("duration_min"))
        if not d or not t or d <= 0:
            continue
        bucket = _pace_bucket(d)
        if bucket is None:
            continue
        pace = round(t / d, 2)
        if bucket not in prs or pace < prs[bucket]["pace_min_per_km"]:
            prs[bucket] = {"pace_min_per_km": pace, "distance_km": d,
                           "duration_min": t, "date": str(s.get("date", ""))[:10]}
    return prs
