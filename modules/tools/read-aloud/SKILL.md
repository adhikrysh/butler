---
name: read-aloud
description: Read a web article or pasted text aloud as Telegram voice messages (Cartesia, Theo's voice). Use when adhi says "read this", "say this", "voice this", "read it to me" with a link or text.
version: 0.1.0
metadata:
  hermes:
    tags: [audio, tts, reading]
    category: tools
    requires_toolsets: [terminal]
---

# Read Aloud

When adhi sends a **link** or **text** and asks you to read / say / voice it aloud:

1. Pick the source:
   - **A URL** → use `--url`.
   - **Pasted text** → write it to a temp file and use `--file` (don't try to pass long
     text as a shell argument — quoting will break).

2. Run the script. It scrapes (if a URL), chunks the text, synthesizes Theo's voice via
   Cartesia, and **sends the voice notes to adhi itself** — you don't handle audio:

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

4. If the script exits non-zero (couldn't fetch/extract a page), tell him plainly. For a
   link that failed extraction, you may retry by fetching the page text yourself with the
   **tinyfish `fetch_content`** tool and passing it via `--file`.

Never print the Cartesia key or the bot token.
