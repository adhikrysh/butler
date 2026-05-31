# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31", "beautifulsoup4>=4.12"]
# ///
"""Fetch a random, not-recently-served letter from the Steve Jobs Archive.

Prints one JSON object to stdout:
  {"id","title","author","date","url","text"}
On failure: a one-line reason to stderr and a non-zero exit code.

The archive (letters.stevejobsarchive.com) is a Next.js site: the homepage
links each letter at /<slug>, and each letter page server-renders its body as
<p class="letter-p"> inside <div class="letter-txt">, with structured metadata
in the __NEXT_DATA__ JSON (props.pageProps.letter: name/date/slug).
"""
import json
import os
import random
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://letters.stevejobsarchive.com"
# Single-segment routes that are NOT letters.
NON_LETTER = {"", "about", "credits", "index", "volume-1", "volume-2", "volume-3", "volume-4"}
SLUG_RE = re.compile(r"^/([a-z0-9]+(?:-[a-z0-9]+)*)/?$")
DEFAULT_STATE = Path(__file__).resolve().parent.parent / "state" / "served.json"
HEADERS = {"User-Agent": "butler-letter/1.0 (+personal Hermes butler)"}


def _get(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def list_slugs(index_html: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    slugs: list[str] = []
    for a in soup.find_all("a", href=True):
        m = SLUG_RE.match(a["href"].strip())
        if not m:
            continue
        slug = m.group(1)
        if slug in NON_LETTER or slug in slugs:
            continue
        slugs.append(slug)
    return slugs


def _next_data(soup: BeautifulSoup) -> dict:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return {}
    try:
        return json.loads(tag.string)
    except ValueError:
        return {}


def parse_letter(slug: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # Body: the server-rendered letter paragraphs.
    paras = [p.get_text(" ", strip=True) for p in soup.select("div.letter-txt p.letter-p")]
    if not paras:  # fallback if the wrapper class ever changes
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p", class_="letter-p")]
    text = "\n\n".join(p for p in paras if p)
    # Metadata from __NEXT_DATA__, with safe fallbacks.
    pp = (_next_data(soup).get("props", {}) or {}).get("pageProps", {}) or {}
    letter = pp.get("letter", {}) or {}
    author = letter.get("name") or slug.replace("-", " ").title()
    date = letter.get("date") or ""
    title = pp.get("title") or f"{author} — Letters to a Young Creator"
    return {
        "id": slug,
        "title": title,
        "author": author,
        "date": date,
        "url": f"{BASE}/{slug}",
        "text": text,
    }


def load_served(path) -> list[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [str(x) for x in data] if isinstance(data, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


def save_served(path, served: list[str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(served), encoding="utf-8")


def pick_unserved(pool: list[str], served: list[str]) -> str:
    remaining = [s for s in pool if s not in set(served)]
    if not remaining:  # full exhaustion -> reset history
        remaining = list(pool)
    return random.choice(remaining)


def main() -> int:
    state_path = Path(os.environ.get("BUTLER_LETTER_STATE", str(DEFAULT_STATE)))
    try:
        slugs = list_slugs(_get(BASE + "/"))
        if not slugs:
            print("no letters found on index page", file=sys.stderr)
            return 1
        served = load_served(state_path)
        if set(slugs).issubset(set(served)):  # exhausted -> reset
            served = []
        choice = pick_unserved(slugs, served)
        letter = parse_letter(choice, _get(f"{BASE}/{choice}"))
        if not letter["text"]:
            print(f"empty letter body for {choice}", file=sys.stderr)
            return 1
        save_served(state_path, served + [choice])
        json.dump(letter, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except requests.RequestException as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
