---
name: steve-jobs-letter
description: Deliver a letter from the Steve Jobs Archive "Letters to a Young Creator". Use when the user asks for today's letter / a Steve Jobs letter, or when the daily 07:00 job runs.
version: 0.1.0
metadata:
  hermes:
    tags: [daily, inspiration, reading]
    category: daily
    requires_toolsets: [terminal]
---

# Steve Jobs Letter

> The scheduled daily 7am push is handled by a separate **no-agent** cron script
> (verbatim, no LLM). This skill is for **interactive** requests only — when the user
> asks you for a letter in chat.

When the user asks for "today's letter" / a Steve Jobs letter:

1. Run the fetch script (absolute path, works from any directory):

   ```
   uv run /home/drc/butler/modules/daily/steve-jobs-letter/scripts/fetch_letter.py
   ```

   It prints ONE JSON object: `{id, title, author, date, url, text}`.
   If it exits non-zero (network/site change), tell the user you couldn't fetch
   today's letter and stop — do not invent a letter.

2. Compose a short Telegram message:
   - One warm opening line naming the author (e.g. "Today's letter is from Jony Ive ✍️").
   - Then the full letter `text`, keeping its paragraph breaks. Do NOT summarize,
     shorten, or editorialize it.
   - End with the `url` on its own line.

3. Keep it Telegram-friendly: plain text, no markdown tables.
