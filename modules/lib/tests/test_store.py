import json
from store import Store, table_name


class FakeSheet:
    """Records write-through calls; can be told to raise (best-effort test)."""
    def __init__(self, boom=False):
        self.calls = []
        self.boom = boom
    def _rec(self, name, *a, **k):
        self.calls.append((name, a, k))
        if self.boom:
            raise RuntimeError("sheet down")
    def ensure_tab(self, *a, **k): self._rec("ensure_tab", *a, **k)
    def append(self, *a, **k): self._rec("append", *a, **k)
    def append_colored(self, *a, **k): self._rec("append_colored", *a, **k)
    def update(self, *a, **k): self._rec("update", *a, **k)


def _store(tmp_path, sheet=None):
    return Store(db_path=str(tmp_path / "t.db"), sheet=sheet)


def test_table_name_sanitizes():
    assert table_name("Jim") == "jim"
    assert table_name("ppl-index") == "ppl_index"
    assert table_name("cold-outbounds") == "cold_outbounds"
    assert table_name("superforecasting") == "superforecasting"


def test_records_missing_table_is_empty(tmp_path):
    assert _store(tmp_path).records("Jim") == []


def test_append_then_records_roundtrip_in_order(tmp_path):
    s = _store(tmp_path)
    s.ensure_tab("Jim", ["a"])
    s.append("Jim", {"a": "1", "u": "é"})
    s.append("Jim", {"a": "2"})
    assert s.records("Jim") == [{"a": "1", "u": "é"}, {"a": "2"}]


def test_update_match_merge_and_none(tmp_path):
    s = _store(tmp_path)
    s.ensure_tab("t", ["k"])
    s.append("t", {"k": "x", "v": "1"})
    s.append("t", {"k": "y", "v": "2"})
    assert s.update("t", {"k": "y"}, {"v": "9"}) == {"k": "y", "v": "9"}
    assert s.records("t")[1] == {"k": "y", "v": "9"}
    assert s.update("t", {"k": "nope"}, {"v": "0"}) is None


def test_json_fidelity_nested(tmp_path):
    s = _store(tmp_path)
    s.ensure_tab("t", [])
    rec = {"x": "1", "nested": json.dumps({"deep": [1, 2]})}
    s.append("t", rec)
    assert s.records("t")[0] == rec


def test_writethrough_projects_to_sheet(tmp_path):
    fake = FakeSheet()
    s = _store(tmp_path, sheet=fake)
    s.ensure_tab("Jim", ["a"])
    s.append("Jim", {"a": "1"})
    s.append_colored("Jim", {"a": "2"}, background={"red": 1})
    s.update("Jim", {"a": "1"}, {"a": "1b"})
    names = [c[0] for c in fake.calls]
    assert names == ["ensure_tab", "append", "append_colored", "update"]


def test_sheet_failure_never_breaks_db_write(tmp_path):
    s = _store(tmp_path, sheet=FakeSheet(boom=True))
    s.ensure_tab("Jim", ["a"])
    s.append("Jim", {"a": "1"})           # sheet raises internally; must not propagate
    assert s.records("Jim") == [{"a": "1"}]   # DB write still succeeded


def test_append_auto_creates_table(tmp_path):
    s = Store(db_path=str(tmp_path / "t.db"), sheet=None)
    s.append("brand-new", {"x": "1"})       # no ensure_tab first
    assert s.records("brand-new") == [{"x": "1"}]
