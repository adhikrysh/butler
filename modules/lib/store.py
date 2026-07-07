"""Local SQLite store — source of truth for the Sheet-backed modules.

Same method surface as lib/sheets.Sheet (records/append/append_colored/update/
ensure_tab/tabs), so a module swaps Sheet() -> Store() with no other change and
gets fast local reads. Writes hit SQLite first (authoritative, WAL) then project
best-effort to the Google Sheet (a human-visible view) — a Sheet failure never
fails the DB write. One table per tab; each row = one record as a JSON object in
`data` (preserves the modules' dynamic-columns style). sqlite3 is stdlib; gspread
is only pulled in (lazily, via lib/sheets) for the Sheet projection.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

DEFAULT_DB = os.path.expanduser("~/.hermes/profiles/butler/state/butler.db")


def table_name(tab: str) -> str:
    """Sanitize a tab title into a safe SQL table name (Jim->jim, ppl-index->ppl_index)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", tab).strip("_").lower()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, db_path: str | None = None, sheet="auto"):
        """sheet='auto' -> lazily build a real lib/sheets.Sheet for write-through;
        sheet=None -> DB only (no projection); sheet=<obj> -> use it (tests)."""
        self._path = db_path or os.environ.get("BUTLER_DB_PATH") or DEFAULT_DB
        if self._path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._sheet_mode = sheet            # "auto" | None | object
        self._sheet_obj = sheet if sheet not in ("auto", None) else None

    # --- Sheet write-through (best-effort) ---
    def _sheet(self):
        if self._sheet_mode is None:
            return None
        if self._sheet_obj is None:         # mode == "auto", build once
            try:
                from sheets import Sheet
                self._sheet_obj = Sheet()
            except Exception as exc:
                print(f"store: Sheet unavailable, running DB-only: {exc}", file=sys.stderr)
                self._sheet_mode = None
                return None
        return self._sheet_obj

    def _project(self, method, *args, **kwargs):
        sh = self._sheet()
        if sh is None:
            return
        try:
            getattr(sh, method)(*args, **kwargs)
        except Exception as exc:
            print(f"store: Sheet projection {method} failed (DB is authoritative): {exc}",
                  file=sys.stderr)

    # --- schema ---
    def _create_table(self, t: str):
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{t}" '
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")

    def ensure_tab(self, tab: str, headers: list[str]) -> str:
        t = table_name(tab)
        self._create_table(t)
        self._conn.commit()
        self._project("ensure_tab", tab, headers)
        return tab

    def tabs(self) -> list[str]:
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return [r[0] for r in cur.fetchall()]

    # --- reads (local, no network) ---
    def _rows_with_ids(self, tab: str):
        t = table_name(tab)
        try:
            cur = self._conn.execute(f'SELECT id, data FROM "{t}" ORDER BY id')
        except sqlite3.OperationalError:
            return []                       # table not created yet
        return [(r[0], json.loads(r[1])) for r in cur.fetchall()]

    def records(self, tab: str) -> list[dict]:
        return [d for _id, d in self._rows_with_ids(tab)]

    # --- writes (DB first, then Sheet best-effort) ---
    def _insert(self, tab: str, record: dict):
        t = table_name(tab)
        self._create_table(t)
        now = _now()
        self._conn.execute(
            f'INSERT INTO "{t}" (data, created_at, updated_at) VALUES (?,?,?)',
            (json.dumps(record, ensure_ascii=False), now, now))
        self._conn.commit()

    def append(self, tab: str, record: dict) -> dict:
        self._insert(tab, record)
        self._project("append", tab, record)
        return record

    def append_colored(self, tab: str, record: dict, background=None) -> dict:
        self._insert(tab, record)
        self._project("append_colored", tab, record, background=background)
        return record

    def update(self, tab: str, match: dict, changes: dict) -> dict | None:
        t = table_name(tab)
        for rowid, d in self._rows_with_ids(tab):
            if all(str(d.get(k, "")) == str(v) for k, v in match.items()):
                merged = {**d, **changes}
                self._conn.execute(
                    f'UPDATE "{t}" SET data=?, updated_at=? WHERE id=?',
                    (json.dumps(merged, ensure_ascii=False), _now(), rowid))
                self._conn.commit()
                self._project("update", tab, match, changes)
                return merged
        return None
