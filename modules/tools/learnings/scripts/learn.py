#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Learnings CLI — the agent's queue of proposed skill improvements.

Butler cannot edit its own skills (`skill_manage` is hook-blocked). Instead it
logs what it learns here; the weekly digest surfaces them; the user promotes the
good ones into a skill by hand, via git. Store: an append-only JSONL on the rw
`state/` mount (never the repo). Record: {id, ts, skill, insight, why,
importance, status}. Agent-facing subcommands print JSON to stdout; the cron-
facing `digest` prints human text. Failures -> stderr + nonzero exit.
"""
import os
import sys
import json
import uuid
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from learncore import (find_dup, filter_pending, apply_review, format_digest,
                       IMPORTANCE, STATUS)  # noqa: E402

DEFAULT_PATH = "/home/drc/.hermes/profiles/butler/state/learned/learnings.jsonl"


def store_path():
    return Path(os.environ.get("BUTLER_LEARNED_STATE", DEFAULT_PATH))


def read_records(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip a corrupt line rather than crash the loop
    return out


def append_record(path, rec):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                   encoding="utf-8")
    tmp.replace(path)


def new_id():
    return "L-" + uuid.uuid4().hex[:6]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    p = argparse.ArgumentParser(prog="learn")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="log a learning (dedups against existing)")
    a.add_argument("--json", required=True, dest="payload")

    pe = sub.add_parser("pending", help="new learnings at/above an importance floor (JSON)")
    pe.add_argument("--min", default="med", choices=IMPORTANCE)

    ls = sub.add_parser("list", help="browse learnings, all statuses/importances (JSON)")
    ls.add_argument("--skill")
    ls.add_argument("--status", choices=STATUS)

    rv = sub.add_parser("review", help="mark a learning promoted/dismissed by id")
    rv.add_argument("--id", required=True)
    rv.add_argument("--status", required=True, choices=("promoted", "dismissed"))

    sub.add_parser("digest", help="formatted digest of pending med+high; empty if none (cron)")

    args = p.parse_args()
    path = store_path()
    records = read_records(path)

    if args.cmd == "add":
        try:
            rec = json.loads(args.payload)
        except json.JSONDecodeError:
            print("--json must be valid JSON", file=sys.stderr)
            return 1
        if not isinstance(rec, dict):
            print("--json must be a JSON object", file=sys.stderr)
            return 1
        insight = str(rec.get("insight", "")).strip()
        if not insight:
            print("insight is required", file=sys.stderr)
            return 1
        skill = str(rec.get("skill", "general")).strip() or "general"
        importance = str(rec.get("importance", "med")).strip().lower()
        if importance not in IMPORTANCE:
            importance = "med"
        dup = find_dup(records, skill, insight)
        if dup is not None:
            print(json.dumps({"deduped": True, "existing": dup}, ensure_ascii=False))
            return 0
        stored = {
            "id": new_id(),
            "ts": now_iso(),
            "skill": skill,
            "insight": insight,
            "why": str(rec.get("why", "")).strip(),
            "importance": importance,
            "status": "new",
        }
        append_record(path, stored)
        print(json.dumps(stored, ensure_ascii=False))

    elif args.cmd == "pending":
        print(json.dumps(filter_pending(records, args.min), indent=2, ensure_ascii=False))

    elif args.cmd == "list":
        out = records
        if args.skill:
            out = [r for r in out if r.get("skill") == args.skill]
        if args.status:
            out = [r for r in out if r.get("status") == args.status]
        print(json.dumps(out, indent=2, ensure_ascii=False))

    elif args.cmd == "review":
        new_records, found = apply_review(records, args.id, args.status)
        if not found:
            print(f"no learning with id {args.id}", file=sys.stderr)
            return 1
        write_records(path, new_records)
        print(json.dumps({"id": args.id, "status": args.status}, ensure_ascii=False))

    elif args.cmd == "digest":
        text = format_digest(filter_pending(records, "med"))
        if text:
            print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
