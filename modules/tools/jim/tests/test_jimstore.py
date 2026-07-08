# modules/tools/jim/tests/test_jimstore.py
from jimstore import JimStore


def _store(tmp_path):
    return JimStore(db_path=str(tmp_path / "j.db"), sheet=None)


def test_log_session_writes_sessions_and_per_set(tmp_path):
    s = _store(tmp_path)
    sid = s.log_session(
        {"type": "strength", "title": "Leg day", "duration_min": 60, "rpe": 8, "feel": "first"},
        [{"exercise": "leg extension", "sets": [{"weight": 80, "reps": 8}, {"weight": 140, "reps": 8}]}])
    assert isinstance(sid, int)
    sess = s.sessions()
    assert len(sess) == 1 and sess[0]["title"] == "Leg day" and sess[0]["type"] == "strength"
    recs = s.set_records()
    assert len(recs) == 2                         # per-set granularity
    assert recs[0]["exercise"] == "leg extension" and recs[0]["session_id"] == sid
    assert recs[1]["e1rm"] is not None            # e1rm computed on write


def test_set_programme_activates_latest_only(tmp_path):
    s = _store(tmp_path)
    s.set_programme({"name": "A", "freq_per_week": 4, "days": []})
    s.set_programme({"name": "B", "freq_per_week": 5, "days": []})
    progs = s.programmes()
    active = [p for p in progs if str(p["active"]) == "1"]
    assert len(active) == 1 and active[0]["name"] == "B"   # only the latest is active


def test_goals_add_and_update(tmp_path):
    s = _store(tmp_path)
    s.add_goal({"metric": "bodyweight", "target": "75", "current": "68", "unit": "kg", "status": "active"})
    assert s.goals()[0]["metric"] == "bodyweight"
    s.update_goal({"metric": "bodyweight"}, {"current": "70"})
    assert s.goals()[0]["current"] == "70"


def test_reads_empty_before_any_write(tmp_path):
    s = _store(tmp_path)
    assert s.sessions() == [] and s.set_records() == [] and s.programmes() == [] and s.goals() == []


class _BoomSheet:
    def ensure_tab(self, *a, **k): raise RuntimeError("sheet down")
    def append(self, *a, **k): raise RuntimeError("sheet down")
    def append_colored(self, *a, **k): raise RuntimeError("sheet down")
    def update(self, *a, **k): raise RuntimeError("sheet down")
    def _ws(self, *a, **k): raise RuntimeError("sheet down")


def test_sheet_failure_never_breaks_db_write(tmp_path):
    s = JimStore(db_path=str(tmp_path / "j.db"), sheet=_BoomSheet())
    sid = s.log_session({"type": "strength", "title": "X"},
                        [{"exercise": "squat", "sets": [{"weight": 100, "reps": 5}]}])
    assert isinstance(sid, int)
    assert len(s.sessions()) == 1 and len(s.set_records()) == 1   # DB write survived the Sheet blow-up
