import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "learn.py"


def _run(tmp_path, *args):
    env = {**os.environ, "BUTLER_LEARNED_STATE": str(tmp_path / "learnings.jsonl")}
    r = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_add_pending_dedup_review_roundtrip(tmp_path):
    out = _run(tmp_path, "add", "--json", json.dumps(
        {"skill": "ppl-index", "insight": "snippets first",
         "why": "cheaper", "importance": "high"}))
    rec = json.loads(out)
    lid = rec["id"]
    assert rec["status"] == "new" and rec["importance"] == "high" and lid.startswith("L-")

    # dedup: same lesson (different case/spacing) -> no new record
    out2 = _run(tmp_path, "add", "--json", json.dumps(
        {"skill": "ppl-index", "insight": "SNIPPETS  first", "importance": "high"}))
    assert json.loads(out2)["deduped"] is True

    # pending shows exactly the one learning
    assert [r["id"] for r in json.loads(_run(tmp_path, "pending"))] == [lid]

    # digest (text) contains it; review -> dismissed; pending + digest go empty
    assert lid in _run(tmp_path, "digest")
    _run(tmp_path, "review", "--id", lid, "--status", "dismissed")
    assert json.loads(_run(tmp_path, "pending")) == []
    assert _run(tmp_path, "digest") == ""


def test_add_requires_insight(tmp_path):
    env = {**os.environ, "BUTLER_LEARNED_STATE": str(tmp_path / "learnings.jsonl")}
    r = subprocess.run([sys.executable, str(SCRIPT), "add", "--json", json.dumps({"skill": "x"})],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "insight" in r.stderr
