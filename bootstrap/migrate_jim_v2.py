#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6"]
# ///
"""One-time: move jim's Phase-1 generic `jim` JSON rows into the v2 typed tables,
render the 3 new Sheet tabs, and drop the old `jim` table + `Jim` Sheet tab. Idempotent
(skips if jim_sessions already has rows). Parses the old remarks notation "Ex NxR@W; ...".
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules" / "tools" / "jim" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules" / "lib"))
from jimstore import JimStore  # noqa: E402

_SET = re.compile(r"([A-Za-z][A-Za-z '\-]*?)\s+(\d+)\s*[x×]\s*(\d+)\s*@\s*(\d+(?:\.\d+)?)")


def _parse_remarks(remarks):
    """Old '<ex> NxR@W; ...' -> exercises[].sets[] (each NxR@W = N sets of R@W)."""
    by = {}
    for m in _SET.finditer(remarks or ""):
        ex, nsets, reps, w = m.group(1).strip().lower(), int(m.group(2)), int(m.group(3)), float(m.group(4))
        by.setdefault(ex, []).extend({"weight": w, "reps": reps} for _ in range(nsets))
    return [{"exercise": ex, "sets": sets} for ex, sets in by.items()]


def main():
    db = os.environ.get("BUTLER_DB_PATH")
    store = JimStore()
    if store.sessions():
        print(f"skip: jim_sessions already has {len(store.sessions())} rows")
        return 0
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    try:
        old = [dict(r) for r in c.execute("SELECT data FROM jim ORDER BY id")]
    except sqlite3.OperationalError:
        old = []
    for row in old:
        d = json.loads(row["data"])
        exercises = _parse_remarks(d.get("remarks", "")) if d.get("type") == "strength" else []
        store.log_session(
            {"type": d.get("type", "other"), "title": d.get("title"), "date": d.get("datetime"),
             "rpe": d.get("rpe"), "feel": d.get("remarks")}, exercises)
    print(f"migrated {len(old)} old jim rows -> {len(store.sessions())} sessions, "
          f"{len(store.set_records())} sets")
    # retire the old generic table + Sheet tab
    try:
        c.execute("DROP TABLE IF EXISTS jim"); c.commit()
    except Exception as exc:
        print(f"drop old table: {exc}", file=sys.stderr)
    try:
        from sheets import Sheet
        sh = Sheet()
        if "Jim" in sh.tabs():
            sh._ss.del_worksheet(sh._ws("Jim"))
            print("deleted old 'Jim' Sheet tab")
    except Exception as exc:
        print(f"old tab cleanup: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
