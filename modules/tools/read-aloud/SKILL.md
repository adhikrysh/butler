---
name: read-aloud
description: Read a web article or pasted text aloud as Telegram voice messages (Cartesia, Ronald's voice). Use when the user says "read this", "say this", "voice this", "read it to me" with a link or text.
version: 0.1.0
metadata:
  hermes:
    tags: [audio, tts, reading]
    category: tools
    requires_toolsets: [terminal]
---

# Read Aloud

When the user sends a **link** or **text** and asks you to read / say / voice it aloud:

1. Pick the source:
   - **A URL** → use `--url`.
   - **Pasted text** → write it to a temp file and use `--file` (don't try to pass long
     text as a shell argument — quoting will break).

2. Run the script. It scrapes (if a URL), chunks the text, synthesizes Ronald's voice via
   Cartesia, and **sends the voice notes to the user itself** — you don't handle audio:

   ```
   # URL:
   uv run /home/drc/butler/modules/tools/read-aloud/scripts/speak.py --url "<link>"

   # Pasted text — write it first, then:
   #   (save the text to /tmp/readaloud.txt)
   uv run /home/drc/butler/modules/tools/read-aloud/scripts/speak.py --file /tmp/readaloud.txt
   ```

3. Reply briefly so he knows it's coming, e.g. **"🔊 Reading it now — first part's on its
   way."** The voice notes auto-play in order; he sets 1.5× once with Telegram's speed
   button and it sticks.

4. For long articles, prefer extracting the page text first with `mcp_tinyfish_fetch_content`
   and then chunking the extracted text for narration. See `references/web-article-fallback.md`
   for a reliable fallback path.

5. If the canonical script exits non-zero or is unavailable, tell him plainly and use the
   extracted-text fallback rather than stopping.

Never print the Cartesia key or the bot token.
