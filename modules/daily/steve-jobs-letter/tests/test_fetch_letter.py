import json
from pathlib import Path

import fetch_letter as fl

FIX = Path(__file__).parent / "fixtures"


def test_list_slugs_finds_letters_and_excludes_nav():
    slugs = fl.list_slugs((FIX / "index.html").read_text(encoding="utf-8"))
    assert "jony-ive" in slugs
    assert "tim-cook" in slugs
    # Nav / volume / about routes must NOT be treated as letters
    for bad in ("", "about", "volume-1", "volume-2"):
        assert bad not in slugs
    assert len(slugs) >= 20


def test_parse_letter_extracts_body_and_metadata():
    letter = fl.parse_letter("jony-ive", (FIX / "letter_jony_ive.html").read_text(encoding="utf-8"))
    assert letter["id"] == "jony-ive"
    assert letter["url"] == "https://letters.stevejobsarchive.com/jony-ive"
    assert letter["author"] == "Jony Ive"
    assert letter["date"] == "2024-09-11"
    assert "working with Steve Jobs" in letter["text"]
    assert len(letter["text"]) > 800
    assert set(letter) == {"id", "title", "author", "date", "url", "text"}


def test_pick_unserved_excludes_served_and_resets_when_exhausted():
    pool = ["a", "b", "c"]
    assert fl.pick_unserved(pool, served=["a", "b"]) == "c"
    # When all served, history resets and any item is eligible
    assert fl.pick_unserved(pool, served=["a", "b", "c"]) in pool


def test_served_roundtrip(tmp_path):
    p = tmp_path / "served.json"
    fl.save_served(p, ["x"])
    assert fl.load_served(p) == ["x"]
    # Missing / corrupt files => empty history (never crash the morning job)
    assert fl.load_served(tmp_path / "missing.json") == []
    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    assert fl.load_served(tmp_path / "bad.json") == []
