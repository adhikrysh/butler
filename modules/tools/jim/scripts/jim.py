#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6", "garminconnect>=0.2.20", "tzdata"]
# ///
"""jim — personal-coach CLI over the `Jim` tab of the butler spreadsheet.

Subcommands print JSON (interactive) to stdout; failures -> stderr + nonzero.
Header row = schema. Columns: datetime, type, title, duration_min, distance_km,
avg_hr, calories, rpe, garmin_activity_id, remarks.

Garmin is best-effort everywhere: a flaky watch/sync never blocks a write.
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from sheets import Sheet  # noqa: E402
import garmin as gm       # noqa: E402
from jimcore import compute_prs, latest_by_type, latest_goals, recent_sessions  # noqa: E402

TAB = "Jim"
HEADERS = ["datetime", "type", "title", "duration_min", "distance_km",
           "avg_hr", "calories", "rpe", "garmin_activity_id", "remarks"]
META_YELLOW = {"red": 1.0, "green": 0.949, "blue": 0.8}   # ~#FFF2CC
PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_DIR = Path(os.environ.get(
    "BUTLER_JIM_STATE", str(Path.home() / ".hermes/profiles/butler/state/jim")))
# map a jim cardio type -> Garmin activityType keywords, for safe auto-matching
_TYPE_KEYWORDS = {"run": ("run",), "ride": ("cycl", "bik", "ride"), "swim": ("swim",)}


def _now():
    return datetime.now(PACIFIC).strftime("%Y-%m-%dT%H:%M")


def _mirror(record: dict):
    """Append the record to the jsonl mirror (best-effort; never fatal)."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with (STATE_DIR / "log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"captured_at": datetime.now(timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%SZ"), **record}) + "\n")
    except Exception as exc:   # never let the mirror (fs or serialization) fail a write
        print(f"jsonl mirror failed: {exc}", file=sys.stderr)


def _garmin_readiness():
    """Best-effort: today's training readiness score/level, else None."""
    try:
        g = gm.client()
        today = datetime.now(PACIFIC).date().isoformat()
        tr_list = gm.training_readiness(g, today)
        tr = max(tr_list, key=lambda x: x.get("timestamp", "")) if tr_list else {}
        sync_ms, device = gm.last_sync(g)
        return {"readiness": tr.get("score"), "level": tr.get("level"),
                "last_sync_ms": sync_ms, "device": device}
    except Exception as exc:
        return {"garmin_error": str(exc)}


def _enrich_from_garmin(rec: dict):
    """If the session looks like cardio, attach the matching Garmin activity's
    metrics. Best-effort — a failure leaves the row as-is (log never lost)."""
    try:
        g = gm.client()
        # trigger a sync if a jim-scoped trigger is configured, then gate briefly
        trig = os.environ.get("JIM_SYNC_CMD")
        gm.ensure_fresh_sync(g, trigger_cmd=trig,
                             timeout=int(os.environ.get("JIM_SYNC_TIMEOUT", "60")),
                             poll=int(os.environ.get("JIM_SYNC_POLL", "10")))
        today = datetime.now(PACIFIC).date().isoformat()
        acts = [gm.summarize_activity(a) for a in gm.activities(g, today, today)]
        want_id = rec.get("garmin_activity_id")
        match = None
        if want_id:
            match = next((a for a in acts if str(a["garmin_activity_id"]) == str(want_id)), None)
        else:
            kws = _TYPE_KEYWORDS.get(str(rec.get("type", "")).lower(), ())
            typed = [a for a in acts if any(k in str(a.get("type") or "").lower() for k in kws)]
            if typed:
                match = typed[-1]        # most recent activity of the matching type
            elif len(acts) == 1:
                match = acts[0]          # unambiguous: only one activity logged today
            # else: ambiguous (multiple, none same-type) -> don't guess; wait for an explicit id
        if match:
            rec.setdefault("garmin_activity_id", match["garmin_activity_id"])
            for k_src, k_dst in (("distance_km", "distance_km"), ("avg_hr", "avg_hr"),
                                 ("calories", "calories"), ("duration_min", "duration_min")):
                if not rec.get(k_dst) and match.get(k_src) is not None:
                    rec[k_dst] = match[k_src]
    except Exception as exc:
        print(f"garmin enrich skipped: {exc}", file=sys.stderr)
    return rec


def main() -> int:
    p = argparse.ArgumentParser(prog="jim")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="append a training session")
    lg.add_argument("--json", required=True, dest="payload")
    lg.add_argument("--no-garmin", action="store_true", help="skip Garmin enrichment")

    nt = sub.add_parser("note", help="append a yellow meta-row (goal/plan/note)")
    nt.add_argument("--type", required=True, choices=["goal", "plan", "note"])
    nt.add_argument("--text", required=True)
    nt.add_argument("--title", default="")

    sub.add_parser("current", help="coach context blob (plan+goals+recent+PRs+readiness)")
    sub.add_parser("prs", help="computed PRs")
    sub.add_parser("dump", help="whole tab as JSON")

    args = p.parse_args()
    s = Sheet()
    s.ensure_tab(TAB, HEADERS)

    if args.cmd == "log":
        rec = json.loads(args.payload)
        rec.setdefault("datetime", _now())
        rec.setdefault("type", "other")
        if not args.no_garmin and str(rec.get("type", "")).lower() in ("run", "ride", "swim"):
            rec = _enrich_from_garmin(rec)
        s.append(TAB, rec)
        _mirror(rec)
        print(json.dumps(rec, ensure_ascii=False))

    elif args.cmd == "note":
        rec = {"datetime": _now(), "type": args.type,
               "title": args.title, "remarks": args.text}
        s.append_colored(TAB, rec, background=META_YELLOW)
        _mirror(rec)
        print(json.dumps(rec, ensure_ascii=False))

    elif args.cmd == "current":
        rows = s.records(TAB)
        print(json.dumps({
            "plan": latest_by_type(rows, "plan"),
            "goals": latest_goals(rows),
            "recent_sessions": recent_sessions(rows, 7),
            "prs": compute_prs(rows),
            "garmin": _garmin_readiness(),
        }, indent=2, ensure_ascii=False))

    elif args.cmd == "prs":
        print(json.dumps(compute_prs(s.records(TAB)), indent=2, ensure_ascii=False))

    elif args.cmd == "dump":
        print(json.dumps(s.records(TAB), indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
