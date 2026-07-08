#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6", "garminconnect>=0.2.20", "tzdata"]
# ///
"""jim v2 CLI — structured training log/programme/goals over jimstore (SQLite) + Garmin.

The AGENT structures freeform input into records and passes JSON; this CLI never parses
natural-language sets. Reads are local (DB); Garmin/Sheet are best-effort (never block a write).
"""
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import garmin as gm            # noqa: E402
from jimstore import JimStore  # noqa: E402
import jimcore                 # noqa: E402

PACIFIC = ZoneInfo("America/Los_Angeles")


def _garmin_readiness():
    try:
        g = gm.client()
        today = datetime.now(PACIFIC).date().isoformat()
        tr = gm.training_readiness(g, today)
        best = max(tr, key=lambda x: x.get("timestamp", "")) if tr else {}
        sync_ms, dev = gm.last_sync(g)
        return {"readiness": best.get("score"), "level": best.get("level"),
                "last_sync_ms": sync_ms, "device": dev}
    except Exception as exc:
        return {"garmin_error": str(exc)}


def _enrich_session(rec):
    """Best-effort: fill session fields from the matching Garmin activity.

    Wraps client acquisition too, so a Garmin-down state never blocks the
    DB write — any failure just leaves `rec` unchanged.
    """
    try:
        g = gm.client()
        return gm.enrich_session(g, rec, sync_cmd=os.environ.get("JIM_SYNC_CMD"))
    except Exception as exc:
        print(f"garmin enrich skipped: {exc}", file=sys.stderr)
    return rec


def main() -> int:
    p = argparse.ArgumentParser(prog="jim")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("log", "plan", "goal"):
        sp = sub.add_parser(name); sp.add_argument("--json", required=True, dest="payload")
    gu = sub.add_parser("goal-update"); gu.add_argument("--match", required=True); gu.add_argument("--json", required=True, dest="payload")
    pr = sub.add_parser("progress"); pr.add_argument("--exercise", default=None)
    for name in ("current", "prs", "dump", "resync"):
        sub.add_parser(name)

    args = p.parse_args()
    s = JimStore()

    if args.cmd == "log":
        rec = json.loads(args.payload)
        exercises = rec.pop("exercises", [])
        rec.setdefault("date", datetime.now(PACIFIC).isoformat(timespec="minutes"))
        rec = _enrich_session(rec)
        sid = s.log_session(rec, exercises)
        print(json.dumps({"logged_session": sid, "type": rec.get("type")}, ensure_ascii=False))

    elif args.cmd == "plan":
        print(json.dumps({"programme": s.set_programme(json.loads(args.payload))}))

    elif args.cmd == "goal":
        print(json.dumps({"goal": s.add_goal(json.loads(args.payload))}))

    elif args.cmd == "goal-update":
        res = s.update_goal(json.loads(args.match), json.loads(args.payload))
        print(json.dumps(res, ensure_ascii=False) if res else json.dumps({"updated": None}))

    elif args.cmd == "current":
        recs = s.set_records()
        print(json.dumps({
            "programme": jimcore.latest_active(s.programmes()),
            "goals": jimcore.active_goals(s.goals()),
            "recent_sessions": s.sessions()[-7:],
            "prs": {"lifts": jimcore.compute_prs(recs), "cardio": jimcore.compute_cardio_prs(s.sessions())},
            "garmin": _garmin_readiness(),
        }, indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "progress":
        recs = s.set_records()
        out = {"prs": {"lifts": jimcore.compute_prs(recs), "cardio": jimcore.compute_cardio_prs(s.sessions())},
               "adherence": jimcore.weekly_adherence(s.sessions(),
                            jimcore.latest_active(s.programmes()) or {}, datetime.now(PACIFIC).date())}
        if args.exercise:
            out["progression"] = jimcore.progression(recs, args.exercise)
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "prs":
        print(json.dumps({"lifts": jimcore.compute_prs(s.set_records()), "cardio": jimcore.compute_cardio_prs(s.sessions())}, indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "dump":
        print(json.dumps({"sessions": s.sessions(), "sets": s.set_records(),
                          "programmes": s.programmes(), "goals": s.goals()},
                         indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "resync":
        s.render_sheets()
        print(json.dumps({"resynced": len(s.sessions())}))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
