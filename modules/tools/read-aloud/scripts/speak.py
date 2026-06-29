# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31", "trafilatura>=1.8", "imageio-ffmpeg>=0.5"]
# ///
"""Read a web article or pasted text aloud as Telegram voice messages.

Pipeline: source (url -> trafilatura | file/stdin) -> chunk (coarse, tiny first
chunk for a fast start) -> Cartesia TTS (sonic, Ronald voice) mp3 -> ffmpeg
opus/ogg (static binary via imageio-ffmpeg, no system ffmpeg needed) -> Telegram
sendVoice. One voice note per chunk, sent the moment it's encoded, so Telegram
auto-plays them through in order.

Usage:
  speak.py --url https://example.com/article
  speak.py --file /tmp/text.txt
  echo "some text" | speak.py

Env (from profile .env): CARTESIA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS.
Optional: CARTESIA_VOICE_ID (default Ronald), CARTESIA_MODEL (default sonic-2),
READALOUD_MAX_CHARS (700), READALOUD_FIRST_CHARS (250).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import requests

CARTESIA_TTS = "https://api.cartesia.ai/tts/bytes"
CARTESIA_VERSION = "2024-11-13"
RONALD = "5ee9feff-1265-424a-9d7f-8e4d431a12c7"  # Cartesia "Ronald - Thinker"
MAX_CHARS = int(os.environ.get("READALOUD_MAX_CHARS", "700"))
FIRST_CHARS = int(os.environ.get("READALOUD_FIRST_CHARS", "250"))

_WS = re.compile(r"[ \t]+")
_SENT = re.compile(r"(?<=[.!?])\s+")


def get_text(args) -> tuple[str, str | None]:
    """Return (text, title). Raises on fetch/extract failure or empty input."""
    if args.url:
        import trafilatura
        html = trafilatura.fetch_url(args.url)
        if not html:
            raise RuntimeError(f"could not fetch {args.url}")
        out = trafilatura.extract(html, output_format="json",
                                  include_comments=False, include_tables=False)
        if not out:
            raise RuntimeError("could not extract readable article text")
        doc = json.loads(out)
        text = (doc.get("text") or "").strip()
        if len(text) < 200:
            raise RuntimeError("extracted text too short to be an article")
        return text, doc.get("title")
    raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    if not raw.strip():
        raise RuntimeError("no input text")
    return raw.strip(), args.title


def chunk_text(text: str, max_chars: int = MAX_CHARS, first_chars: int = FIRST_CHARS) -> list[str]:
    """Coarse chunks on sentence boundaries; first chunk small for a fast start.
    Pure function (no I/O) so it's unit-testable."""
    text = _WS.sub(" ", text.replace("\r", "")).strip()
    sentences = [s.strip() for s in _SENT.split(text) if s.strip()]
    chunks: list[str] = []
    cur, limit = "", first_chars
    for s in sentences:
        if cur and len(cur) + 1 + len(s) > limit:
            chunks.append(cur)
            cur, limit = "", max_chars
        while len(s) > limit:  # a single overlong sentence: hard-split it
            chunks.append(s[:limit])
            s, limit = s[limit:], max_chars
        cur = f"{cur} {s}".strip() if cur else s
    if cur:
        chunks.append(cur)
    return chunks


def synth(text: str, key: str, voice: str, model: str) -> bytes:
    """Cartesia TTS -> mp3 bytes."""
    r = requests.post(CARTESIA_TTS, timeout=60, headers={
        "X-API-Key": key,
        "Cartesia-Version": CARTESIA_VERSION,
        "Content-Type": "application/json",
    }, json={
        "model_id": model,
        "transcript": text,
        "voice": {"mode": "id", "id": voice},
        "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
        "language": "en",
    })
    r.raise_for_status()
    return r.content


def to_opus(ff: str, mp3: bytes) -> str:
    """Convert mp3 bytes -> ogg/opus file (what Telegram sendVoice needs). Returns path."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as m:
        m.write(mp3)
        mp3_path = m.name
    ogg_path = mp3_path[:-4] + ".ogg"
    subprocess.run([ff, "-y", "-i", mp3_path, "-c:a", "libopus", "-b:a", "32k",
                    "-ar", "48000", "-ac", "1", ogg_path], check=True, capture_output=True)
    os.unlink(mp3_path)
    return ogg_path


def send_voice(token: str, chat: str, ogg: str) -> bool:
    for _ in range(2):  # one retry
        try:
            with open(ogg, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendVoice", timeout=60,
                    data={"chat_id": chat}, files={"voice": ("part.ogg", f, "audio/ogg")})
            if r.json().get("ok"):
                return True
        except Exception:
            pass
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--file")
    ap.add_argument("--title")
    ap.add_argument("--voice", default=os.environ.get("CARTESIA_VOICE_ID", RONALD))
    ap.add_argument("--model", default=os.environ.get("CARTESIA_MODEL", "sonic-2"))
    args = ap.parse_args()

    key = os.environ.get("CARTESIA_API_KEY")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = (os.environ.get("TELEGRAM_ALLOWED_USERS") or "").split(",")[0].strip()
    if not (key and token and chat):
        print("missing CARTESIA_API_KEY / TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOWED_USERS",
              file=sys.stderr)
        return 1
    try:
        text, title = get_text(args)
    except Exception as exc:
        print(f"read failed: {exc}", file=sys.stderr)
        return 2

    chunks = chunk_text(text)
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    sent = 0
    for i, chunk in enumerate(chunks, 1):
        try:
            ogg = to_opus(ff, synth(chunk, key, args.voice, args.model))
            ok = send_voice(token, chat, ogg)
            os.unlink(ogg)
            if ok:
                sent += 1
            else:
                print(f"chunk {i}/{len(chunks)}: sendVoice failed", file=sys.stderr)
        except Exception as exc:
            print(f"chunk {i}/{len(chunks)}: {exc}", file=sys.stderr)
    print(f"sent {sent}/{len(chunks)} voice notes" + (f" — {title}" if title else ""))
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
