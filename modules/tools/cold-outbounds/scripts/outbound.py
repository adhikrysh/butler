#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6"]
# ///
"""Outbound CLI — outreach log + follow-up nudges + email sync over the
`cold-outbounds` tab. Subcommands print to stdout; failures -> stderr + nonzero.
Header row = schema (read live). Shares `sheets.py` (../../../lib) with the other
butler-sheet modules.
"""
import os
import sys
import json
import argparse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from sheets import Sheet  # noqa: E402
from outboundcore import select_nudges, is_bulk, build_threads, derive_status, initiated  # noqa: E402

TAB = "cold-outbounds"


def main() -> int:
    p = argparse.ArgumentParser(prog="outbound")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dump", help="print the cold-outbounds tab as JSON")

    f = sub.add_parser("find", help="search cold-outbounds for a name/company/etc.")
    f.add_argument("query")

    a = sub.add_parser("add", help="append an outreach row to cold-outbounds")
    a.add_argument("--json", required=True, dest="payload")

    u = sub.add_parser("update", help="update first cold-outbounds row matching --match")
    u.add_argument("--match", required=True)
    u.add_argument("--json", required=True, dest="payload")

    sub.add_parser("nudges", help="follow-up digest: cold, unreplied outreach")

    sy = sub.add_parser("sync", help="email→sheet sync (dry-run unless --apply)")
    sy.add_argument("--apply", action="store_true", help="write updates (default: dry-run)")
    sy.add_argument("--since", type=int, default=90, help="lookback window in days")
    sy.add_argument("--limit", type=int, default=300, help="max messages per folder")

    args = p.parse_args()
    s = Sheet()

    if args.cmd == "dump":
        print(json.dumps(s.records(TAB), indent=2, ensure_ascii=False))
    elif args.cmd == "find":
        q = args.query.lower()
        hits = [r for r in s.records(TAB) if q in json.dumps(r, ensure_ascii=False).lower()]
        print(json.dumps(hits, indent=2, ensure_ascii=False))
    elif args.cmd == "add":
        print(json.dumps(s.append(TAB, json.loads(args.payload)), ensure_ascii=False))
    elif args.cmd == "update":
        res = s.update(TAB, json.loads(args.match), json.loads(args.payload))
        if res is None:
            print("no matching row", file=sys.stderr)
            return 1
        print(json.dumps(res, ensure_ascii=False))
    elif args.cmd == "nudges":
        today = date.today()
        due = select_nudges(s.records(TAB), today)
        if not due:
            return 0  # empty stdout => no-agent cron stays silent
        lines = ["📋 Follow-ups due:"]
        for r in due:
            days = (today - date.fromisoformat(str(r["sent_date"])[:10])).days
            plat = r.get("platform", "") or "?"
            reason = f" — {r['reason']}" if r.get("reason") else ""
            lines.append(f"• {r.get('name', '?')} ({plat}, {days}d no reply){reason}")
        print("\n".join(lines))
    elif args.cmd == "sync":
        from mailsource import fetch_all
        mine = {a.strip().lower() for a in
                ([os.environ.get("GMAIL_ADDR", ""), os.environ.get("ICLOUD_ADDR", "")]
                 + os.environ.get("CRM_ALIASES", "").split(","))
                if a.strip()}
        msgs = [m for m in fetch_all(since_days=args.since, limit=args.limit) if not is_bulk(m)]
        threads = build_threads(msgs, mine)
        today = date.today()
        rows = s.records(TAB)
        known = set()
        for r in rows:
            for fld in ("email", "name"):
                v = str(r.get(fld, "")).strip().lower()
                if v:
                    known.add(v)
        updates, matched = [], set()
        for r in rows:
            if str(r.get("platform", "")).strip().lower() not in ("mail", "stanford email"):
                continue
            key = str(r.get("email", "")).strip().lower()
            if not key and "@" in str(r.get("name", "")):
                key = str(r.get("name", "")).strip().lower()
            if not key or key not in threads:
                continue
            matched.add(key)
            th = threads[key]
            st = derive_status(th, today)
            changes = {"replied": "replied" if st["status"] == "replied" else "no reply"}
            if th["last_outbound"]:
                changes["sent_date"] = th["last_outbound"].isoformat()
            if not str(r.get("email", "")).strip():
                changes["email"] = key
            diff = {k: v for k, v in changes.items() if str(r.get(k, "")).strip() != str(v)}
            if diff:
                match = ({"email": str(r.get("email", "")).strip()}
                         if str(r.get("email", "")).strip() else {"name": r.get("name", "")})
                updates.append({"row": r.get("name", "") or key, "match": match, "changes": diff})
        candidates = sorted(
            ({"email": cp, "subject": th["subject"],
              "last_outbound": th["last_outbound"].isoformat(),
              "they_replied": th["last_inbound"] is not None}
             for cp, th in threads.items()
             if th["last_outbound"] and cp not in known and cp not in matched
             and initiated(th["subject"])),
            key=lambda c: c["last_outbound"], reverse=True)[:25]
        result = {"mode": "apply" if args.apply else "dry-run",
                  "scanned": len(msgs), "threads": len(threads),
                  "updates": updates, "new_candidates": candidates}
        if args.apply:
            for upd in updates:
                s.update(TAB, upd["match"], upd["changes"])
            result["applied"] = len(updates)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
