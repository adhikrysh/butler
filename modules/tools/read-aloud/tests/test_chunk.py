"""Unit tests for the read-aloud chunker (pure function, no network)."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "speak", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "speak.py")
speak = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(speak)


def test_first_chunk_small_rest_bounded():
    text = " ".join(f"Sentence number {i} goes here." for i in range(200))
    chunks = speak.chunk_text(text, max_chars=700, first_chars=250)
    assert len(chunks) > 1
    assert len(chunks[0]) <= 250          # fast first chunk
    assert all(len(c) <= 700 for c in chunks)


def test_words_preserved_and_whitespace_normalized():
    text = "Hello world. This is a test.  Multiple   spaces.\n\nNew paragraph here."
    chunks = speak.chunk_text(text, max_chars=700, first_chars=250)
    assert " ".join(chunks).split() == text.split()  # no words lost or invented


def test_no_empty_chunks_with_tiny_limits():
    text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota."
    chunks = speak.chunk_text(text, max_chars=25, first_chars=25)
    assert chunks and all(c.strip() for c in chunks)
    assert all(len(c) <= 25 for c in chunks)


def test_overlong_sentence_hard_split():
    text = "word" * 500  # one 2000-char "sentence", no boundaries
    chunks = speak.chunk_text(text, max_chars=700, first_chars=250)
    assert all(len(c) <= 700 for c in chunks)
    assert "".join(chunks) == text


def test_single_short_text_one_chunk():
    chunks = speak.chunk_text("Just one short line.", max_chars=700, first_chars=250)
    assert chunks == ["Just one short line."]
