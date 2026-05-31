# Module: steve-jobs-letter

- **Type:** proactive (scheduled push)
- **Schedule:** `0 14 * * *` UTC = 7:00am US Pacific (PDT) → Telegram
- **Daily push = NO LLM.** The cron runs in `--no-agent` mode: a script produces
  the final Telegram message and its stdout is delivered **verbatim**. Zero tokens,
  zero latency, and the letter can't be altered/truncated by a model.
  - Cron entrypoint: `cron/deliver.sh` → `scripts/fetch_letter.py --telegram`.
  - Hermes resolves `--script` names under `~/.hermes/profiles/butler/scripts/`,
    so `deliver.sh` is copied there as `steve_jobs_letter.sh` (by `bootstrap/register_cron.sh`).
- **Interactive path:** `SKILL.md` is used only when adhi asks Butler conversationally
  ("today's letter") — there the agent is already in the loop. The script's JSON
  output (`{id,title,author,date,url,text}`) feeds that path.
- **Memory:** none. Runtime state only: `state/served.json` (gitignored; tracks served
  letters, auto-resets once all are exhausted).
- **Cron registration (run once, or via `bootstrap/register_cron.sh`):**
  ```bash
  cp cron/deliver.sh ~/.hermes/profiles/butler/scripts/steve_jobs_letter.sh
  butler cron create "0 14 * * *" --no-agent --script steve_jobs_letter.sh \
    --deliver telegram:<your-id> --name daily-steve-jobs-letter
  ```
- **Tests:**
  ```bash
  cd modules/daily/steve-jobs-letter
  PYTHONPATH=scripts uv run --with beautifulsoup4 --with requests --with pytest pytest tests/ -q
  ```
