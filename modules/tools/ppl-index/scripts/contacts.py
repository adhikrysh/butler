#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6"]
# ///
"""Contacts CLI — the agent's tool surface over the `ppl-index` tab (people the user knows).

Subcommands print JSON to stdout; failures go to stderr + a nonzero exit. Header
row = schema (read live). Shares `sheets.py` (../../../lib) with the other
butler-sheet modules.
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from sheets import Sheet  # noqa: E402

TAB = "ppl-index"


def main() -> int:
    p = argparse.ArgumentParser(prog="contacts")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dump", help="print the ppl-index tab as JSON")

    f = sub.add_parser("find", help="search ppl-index for a name/company/etc.")
    f.add_argument("query")

    a = sub.add_parser("add", help="append a person to ppl-index")
    a.add_argument("--json", required=True, dest="payload")

    u = sub.add_parser("update", help="update first ppl-index row matching --match")
    u.add_argument("--match", required=True)
    u.add_argument("--json", required=True, dest="payload")

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
