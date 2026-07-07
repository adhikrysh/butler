#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6"]
# ///
"""One-time: import each Google Sheet tab into the local SQLite store. Idempotent
(skips a tab whose DB table already has rows). Verifies row counts. Run on the box.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules" / "lib"))
from store import Store  # noqa: E402

TABS = ["Jim", "ppl-index", "cold-outbounds", "superforecasting"]


def migrate(sheet, store, tabs=TABS) -> dict:
    summary = {}
    for tab in tabs:
        if store.records(tab):
            summary[tab] = f"skipped ({len(store.records(tab))} rows already in DB)"
            continue
        try:
            rows = sheet.records(tab)
        except Exception as exc:
            summary[tab] = f"ERROR reading sheet: {exc}"
            continue
        store.ensure_tab(tab, [])
        for r in rows:
            store.append(tab, r)          # store has sheet=None -> DB-only, no re-projection
        got = len(store.records(tab))
        ok = "" if got == len(rows) else "  ⚠️ COUNT MISMATCH"
        summary[tab] = f"imported {got} rows (sheet had {len(rows)}){ok}"
    return summary


def main() -> int:
    from sheets import Sheet
    store = Store(sheet=None)              # DB-only: never write back to the Sheet
    sheet = Sheet()
    print(f"DB: {store._path}")
    for tab, msg in migrate(sheet, store).items():
        print(f"  {tab}: {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
