# modules/tools/jim/scripts/jimstore.py
"""jim's structured store — typed SQLite tables in butler.db + best-effort Sheet render.

jim-owned tables (jim_sessions/jim_sets/jim_programme/jim_goals). DB is the source of
truth; the three Sheet tabs (Jim Sessions/Programme/Goals) are a rendered view derived
here — a Sheet failure never fails a DB write. Per-set granularity in jim_sets makes
progression/PRs/volume queryable. sqlite3 is stdlib; gspread only for the render.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import jimcore

DEFAULT_DB = os.path.expanduser("~/.hermes/profiles/butler/state/butler.db")
SESSIONS_TAB, PROGRAMME_TAB, GOALS_TAB = "Jim Sessions", "Jim Programme", "Jim Goals"
SESSION_COLS = ["date", "type", "title", "summary", "duration_min", "rpe", "feel"]
PROGRAMME_COLS = ["date", "name", "plan", "active"]
GOAL_COLS = ["date_set", "metric", "target", "current", "unit", "deadline", "status"]
_GOAL_WRITABLE = {"date_set", "metric", "target", "current", "unit", "deadline", "status", "notes"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class JimStore:
    def __init__(self, db_path=None, sheet="auto"):
        self._path = db_path or os.environ.get("BUTLER_DB_PATH") or DEFAULT_DB
        if self._path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        self._c = sqlite3.connect(self._path)
        self._c.row_factory = sqlite3.Row
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA busy_timeout=5000")
        self._c.execute("PRAGMA foreign_keys=ON")
        self._schema()
        self._sheet_mode = sheet
        self._sheet_obj = sheet if sheet not in ("auto", None) else None

    def _schema(self):
        self._c.executescript("""
        CREATE TABLE IF NOT EXISTS jim_sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, type TEXT NOT NULL,
          title TEXT, duration_min INTEGER, rpe INTEGER, feel TEXT, distance_km REAL,
          avg_hr INTEGER, calories INTEGER, garmin_activity_id TEXT, bodyweight_kg REAL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jim_sets(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id INTEGER NOT NULL REFERENCES jim_sessions(id) ON DELETE CASCADE,
          exercise TEXT NOT NULL, set_no INTEGER NOT NULL, weight REAL, reps INTEGER,
          e1rm REAL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_sets_exercise ON jim_sets(exercise);
        CREATE TABLE IF NOT EXISTS jim_programme(
          id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, name TEXT,
          plan_json TEXT NOT NULL, plan_text TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          notes TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jim_goals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, date_set TEXT NOT NULL, metric TEXT NOT NULL,
          target TEXT NOT NULL, current TEXT, unit TEXT, deadline TEXT,
          status TEXT NOT NULL DEFAULT 'active', notes TEXT, created_at TEXT NOT NULL);
        """)
        self._c.commit()

    # ---- Sheet render (best-effort) ----
    def _sheet(self):
        if self._sheet_mode is None:
            return None
        if self._sheet_obj is None:
            try:
                from sheets import Sheet
                self._sheet_obj = Sheet()
            except Exception as exc:
                print(f"jimstore: Sheet unavailable, DB-only: {exc}", file=sys.stderr)
                self._sheet_mode = None
                return None
        return self._sheet_obj

    def _render_tab(self, tab, headers, rows):
        sh = self._sheet()
        if sh is None:
            return
        try:
            sh.ensure_tab(tab, headers)
            ws = sh._ws(tab)
            ws.clear()
            ws.update([headers] + rows, value_input_option="USER_ENTERED")
        except Exception as exc:
            print(f"jimstore: render {tab} failed (DB authoritative): {exc}", file=sys.stderr)

    def render_sheets(self):
        try:
            # Sessions
            srows = []
            sets_by = {}
            for r in self.set_records():
                sets_by.setdefault(r["session_id"], []).append(r)
            for s in self.sessions():
                exs = _group_exercises(sets_by.get(s["id"], []))
                summary = jimcore.render_summary(s, exs)
                srows.append([str(s.get("date", "")), str(s.get("type", "")),
                              str(s.get("title", "")), summary, _s(s.get("duration_min")),
                              _s(s.get("rpe")), str(s.get("feel", ""))])
            self._render_tab(SESSIONS_TAB, SESSION_COLS, srows)
            # Programme
            prows = [[str(p["date"]), str(p.get("name", "")), str(p["plan_text"]), _s(p["active"])]
                     for p in self.programmes()]
            self._render_tab(PROGRAMME_TAB, PROGRAMME_COLS, prows)
            # Goals
            grows = [[str(g.get(c, "")) for c in GOAL_COLS] for g in self.goals()]
            self._render_tab(GOALS_TAB, GOAL_COLS, grows)
        except Exception as exc:
            print(f"jimstore: render_sheets failed (DB authoritative): {exc}", file=sys.stderr)

    # ---- writes ----
    def log_session(self, session: dict, exercises: list[dict]) -> int:
        now = _now()
        cur = self._c.execute(
            "INSERT INTO jim_sessions(date,type,title,duration_min,rpe,feel,distance_km,"
            "avg_hr,calories,garmin_activity_id,bodyweight_kg,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (session.get("date") or now[:16], session.get("type", "other"), session.get("title"),
             session.get("duration_min"), session.get("rpe"), session.get("feel"),
             session.get("distance_km"), session.get("avg_hr"), session.get("calories"),
             session.get("garmin_activity_id"), session.get("bodyweight_kg"), now))
        sid = cur.lastrowid
        for e in exercises or []:
            ex = str(e.get("exercise", "")).strip().lower()
            for i, st in enumerate(e.get("sets", []), start=1):
                w, r = st.get("weight"), st.get("reps")
                e1 = jimcore.e1rm(w, r) if (w is not None and r not in (None, "")) else None
                self._c.execute(
                    "INSERT INTO jim_sets(session_id,exercise,set_no,weight,reps,e1rm,created_at)"
                    " VALUES(?,?,?,?,?,?,?)", (sid, ex, i, w, r, e1, now))
        self._c.commit()
        self.render_sheets()
        return sid

    def set_programme(self, plan: dict) -> int:
        now = _now()
        self._c.execute("UPDATE jim_programme SET active=0 WHERE active=1")
        cur = self._c.execute(
            "INSERT INTO jim_programme(date,name,plan_json,plan_text,active,notes,created_at)"
            " VALUES(?,?,?,?,1,?,?)",
            (plan.get("date") or now[:10], plan.get("name"), json.dumps(plan, ensure_ascii=False),
             jimcore.render_plan_text(plan), plan.get("notes"), now))
        self._c.commit()
        self.render_sheets()
        return cur.lastrowid

    def add_goal(self, goal: dict) -> int:
        now = _now()
        cur = self._c.execute(
            "INSERT INTO jim_goals(date_set,metric,target,current,unit,deadline,status,notes,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (goal.get("date_set") or now[:10], goal.get("metric"), goal.get("target"),
             goal.get("current"), goal.get("unit"), goal.get("deadline"),
             goal.get("status", "active"), goal.get("notes"), now))
        self._c.commit()
        self.render_sheets()
        return cur.lastrowid

    def update_goal(self, match: dict, changes: dict) -> dict | None:
        changes = {k: v for k, v in changes.items() if k in _GOAL_WRITABLE}
        if not changes:
            return None
        rows = self.goals()
        for g in rows:
            if all(str(g.get(k, "")) == str(v) for k, v in match.items()):
                sets = ", ".join(f"{k}=?" for k in changes)
                self._c.execute(f"UPDATE jim_goals SET {sets} WHERE id=?",
                                (*changes.values(), g["id"]))
                self._c.commit()
                self.render_sheets()
                return {**g, **changes}
        return None

    # ---- reads (local) ----
    def _rows(self, sql):
        return [dict(r) for r in self._c.execute(sql).fetchall()]

    def sessions(self):
        return self._rows("SELECT * FROM jim_sessions ORDER BY id")

    def set_records(self):
        return self._rows("SELECT s.*, se.date AS date FROM jim_sets s "
                          "JOIN jim_sessions se ON se.id=s.session_id ORDER BY s.id")

    def programmes(self):
        return self._rows("SELECT * FROM jim_programme ORDER BY id")

    def goals(self):
        return self._rows("SELECT * FROM jim_goals ORDER BY id")


def _s(v):
    return "" if v is None else str(v)


def _group_exercises(set_rows):
    """[{exercise,weight,reps,...}] -> [{exercise, sets:[{weight,reps}]}] preserving order."""
    out, idx = [], {}
    for r in set_rows:
        ex = r["exercise"]
        if ex not in idx:
            idx[ex] = len(out)
            out.append({"exercise": ex, "sets": []})
        out[idx[ex]]["sets"].append({"weight": r.get("weight"), "reps": r.get("reps")})
    return out
