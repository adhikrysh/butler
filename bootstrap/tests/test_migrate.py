import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # bootstrap/
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modules" / "lib"))
from store import Store                                                # noqa: E402
from migrate_to_sqlite import migrate                                 # noqa: E402


class FakeSheet:
    def __init__(self, data): self.data = data
    def records(self, tab): return list(self.data.get(tab, []))


def test_migrate_imports_all_rows(tmp_path):
    sheet = FakeSheet({"ppl-index": [{"name": "A"}, {"name": "B"}],
                       "superforecasting": [{"decision": "x"}]})
    store = Store(db_path=str(tmp_path / "m.db"), sheet=None)
    summary = migrate(sheet, store, ["ppl-index", "superforecasting"])
    assert store.records("ppl-index") == [{"name": "A"}, {"name": "B"}]
    assert store.records("superforecasting") == [{"decision": "x"}]
    assert "imported 2" in summary["ppl-index"]


def test_migrate_is_idempotent(tmp_path):
    sheet = FakeSheet({"ppl-index": [{"name": "A"}]})
    store = Store(db_path=str(tmp_path / "m.db"), sheet=None)
    migrate(sheet, store, ["ppl-index"])
    summary = migrate(sheet, store, ["ppl-index"])            # second run
    assert store.records("ppl-index") == [{"name": "A"}]      # not doubled
    assert "skipped" in summary["ppl-index"]
