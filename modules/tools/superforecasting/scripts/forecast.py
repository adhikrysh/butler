#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6"]
# ///
"""Superforecasting decision-journal CLI over the `superforecasting` tab.

Same `butler` spreadsheet as the CRM (CRM_SHEET_ID / CRM_SA_KEY). Subcommands
print to stdout; failures go to stderr + nonzero exit. Header row = schema.
Columns: date, decision, rationale, confidence, expected, review_date, outcome,
verdict, status.
"""
import os
import sys
import json
import argparse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from store import Store  # noqa: E402
from sfcore import parse_window, compute_review_date, select_due, calibration  # noqa: E402

TAB = "superforecasting"


def main() -> int:
    p = argparse.ArgumentParser(prog="forecast")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="append a decision (computes date + review_date)")
    lg.add_argument("--json", required=True, dest="payload")
    lg.add_argument("--window", default="3 months", help="review window if review_date absent")

    sub.add_parser("due", help="decisions due for review (JSON)")

    rv = sub.add_parser("review", help="record outcome/verdict on a decision")
    rv.add_argument("--match", required=True)
    rv.add_argument("--json", required=True, dest="payload")

    sub.add_parser("dump", help="print the whole tab as JSON")
    sub.add_parser("calibration", help="hit-rate by confidence bucket (digest)")
    sub.add_parser("daily", help="daily check-in prompt + due reviews (digest)")

    args = p.parse_args()
    s = Store()
    today = date.today()

    if args.cmd == "log":
        rec = json.loads(args.payload)
        win = rec.pop("window", None) or args.window
        rec.setdefault("date", today.isoformat())
        if not str(rec.get("review_date", "")).strip():
            rec["review_date"] = compute_review_date(
                date.fromisoformat(str(rec["date"])[:10]), parse_window(win)).isoformat()
        rec.setdefault("status", "open")
        print(json.dumps(s.append(TAB, rec), ensure_ascii=False))

    elif args.cmd == "due":
        print(json.dumps(select_due(s.records(TAB), today), indent=2, ensure_ascii=False))

    elif args.cmd == "review":
        res = s.update(TAB, json.loads(args.match), json.loads(args.payload))
        if res is None:
            print("no matching decision", file=sys.stderr)
            return 1
        print(json.dumps(res, ensure_ascii=False))

    elif args.cmd == "dump":
        print(json.dumps(s.records(TAB), indent=2, ensure_ascii=False))

    elif args.cmd == "calibration":
        cal = calibration(s.records(TAB))
        if not cal:
            print("📊 Calibration: not enough reviewed decisions yet — keep logging.")
            return 0
        lines = ["📊 Calibration — your stated confidence vs reality:"]
        for c in cal:
            gap = c["actual"] - c["predicted"]
            tag = "" if abs(gap) <= 10 else ("  ⚠️ overconfident" if gap < 0 else "  ⚠️ underconfident")
            lines.append(f"• ~{c['bucket']}% calls: you said {c['predicted']}%, hit {c['actual']}% (n={c['n']}){tag}")
        print("\n".join(lines))

    elif args.cmd == "daily":
        due = select_due(s.records(TAB), today)
        lines = ["🎯 Decision check-in — any call worth logging today? Reply with it, or “none”."]
        if due:
            lines.append("")
            lines.append("⏰ Due for review — how did these turn out?")
            for r in due:
                line = f"• {r.get('decision', '?')}"
                conf = str(r.get("confidence", "")).strip()
                d = str(r.get("date", "")).strip()
                exp = str(r.get("expected", "")).strip()
                if conf:
                    line += f" (you said {conf})"
                if d:
                    line += f" — logged {d}"
                if exp:
                    line += f"; expected: {exp}"
                lines.append(line)
        print("\n".join(lines))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
