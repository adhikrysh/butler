#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6"]
# ///
"""Snapshot every tab of the `butler` spreadsheet to CSV, for backup.

The Google Sheet is the only app data that lives off the box (in Google's cloud),
so it's the one thing the server's restic→B2 backup can't see. This drops a CSV
per tab into the profile's `state/backups/`, where restic sweeps it with everything
else — giving an owned, encrypted, off-site, point-in-time copy (restic versions the
fixed filenames; no need to timestamp here).

Silent on success (empty stdout → no-agent cron stays quiet). On failure it prints
to stdout so the no-agent cron delivers the alert to Telegram — a silent backup
failure is the dangerous kind.
"""
import csv
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from sheets import Sheet  # noqa: E402

# Absolute default: no-agent crons run with a sandboxed HOME, so never use `~`.
BACKUP_DIR = Path(os.environ.get(
    "BUTLER_BACKUP_DIR", "/home/drc/.hermes/profiles/butler/state/backups"))


def _safe(name: str) -> str:
    return name.replace("/", "-").replace(" ", "-")


def main() -> int:
    try:
        s = Sheet()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        for tab in s.tabs():
            buf = io.StringIO()
            csv.writer(buf).writerows(s.values(tab))
            (BACKUP_DIR / f"{_safe(tab)}.csv").write_text(buf.getvalue(), encoding="utf-8")
    except Exception as exc:
        print(f"⚠️ Sheet backup failed: {exc}")   # stdout → Telegram via the no-agent cron
        return 1
    return 0  # success: silent


if __name__ == "__main__":
    raise SystemExit(main())
