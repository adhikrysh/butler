# Module: read-aloud

- **Type:** interactive tool (agent-invoked; NO cron).
- **What it does:** adhi sends a link or text in chat and asks Butler to read it; Butler
  reads it aloud in **Theo**'s voice (Cartesia) and delivers it as **Telegram voice
  messages** that auto-play start-to-finish.
- **Trigger:** natural language — "read this", "say this", "voice this <link/text>". The
  agent infers intent from `SKILL.md` (interactive path only; there is no scheduled job).
- **Pipeline** (`scripts/speak.py`, self-contained via `uv`):
  source (`--url` → trafilatura | `--file`/stdin) → **chunk** (coarse, ~700 chars; first
  chunk ~250 for a fast start) → **Cartesia** (`sonic-2`, Theo) mp3 → **ffmpeg** opus/ogg
  (static binary via `imageio-ffmpeg` — no system ffmpeg) → **Telegram `sendVoice`**, one
  note per chunk, sent as each is encoded so Telegram auto-advances seamlessly.
- **Latency design:** first note lands in ~5 s; each chunk renders (~15–20 s) far faster
  than it plays (1–3 min), so the next is always waiting → gapless auto-play. Speed is
  Telegram's native voice-note control (set 1.5× once, it sticks).
- **Config / secrets** (profile `.env`, never committed): `CARTESIA_API_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` (chat id). Optional `CARTESIA_VOICE_ID`
  (default Theo `79f8b5fb-2cc8-479a-80df-29f7a7cf1a3e`), `CARTESIA_MODEL` (default `sonic-2`).
- **Errors:** unreadable page → non-zero exit, agent tells adhi (and may retry via tinyfish
  `fetch_content` → `--file`). Per-chunk TTS/encode/send failure → retried once, else
  skipped; the rest still play. Final stdout: `sent N/M voice notes`.
- **Verified live:** Cartesia key + Theo voice, `sonic-2` mp3, `imageio-ffmpeg` libopus
  conversion, and `sendVoice` rendering as a voice message all confirmed working.
- **Test:**
  ```bash
  cd modules/tools/read-aloud
  uv run --with requests --with pytest pytest tests/ -q   # chunker unit tests
  ```
