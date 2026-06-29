# Module: superforecasting

- **Type:** interactive (agent-invoked) + proactive (no-agent crons).
- **What it does:** a decision journal / calibration tool. the user logs decisions with a probability + a falsifiable expected outcome; Butler resurfaces them for review and reports his calibration (stated confidence vs actual hit rate). Implements Tetlock-style superforecasting discipline — the value is the feedback loop, not the log.
- **Sheet:** the `superforecasting` tab of the same `butler` spreadsheet as the CRM. Columns: `date, decision, rationale, confidence, expected, review_date, outcome, verdict, status`. Reuses `CRM_SHEET_ID` + `CRM_SA_KEY`; header-row-is-schema (read live, never positional).
- **Tools:** `scripts/forecast.py` CLI — `log / due / review / dump / calibration / daily` — over `scripts/sheets.py` (generic gspread wrapper, same pattern as CRM) + `scripts/sfcore.py` (pure: window parsing, confidence parsing, due selection, calibration bucketing).
- **Crons (no-agent):** `cron/deliver.sh` → `forecast.py daily` (`0 3 * * *` UTC, ~8pm PT — check-in prompt + due reviews); `cron/calibration.sh` → `forecast.py calibration` (`30 3 * * 1` UTC, Sun ~8:30pm PT — weekly hit-rate report). stdout delivered to Telegram verbatim; replies handled by the agent via `SKILL.md`. Registered in `bootstrap/register_cron.sh`.
- **Tests:** `tests/test_sfcore.py` (pure functions, fixture-based). Run: `cd modules/tools/superforecasting && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q`. Wired into `bootstrap/run_tests.sh`.
- **Habit design:** the daily prompt lowers activation energy (respond, don't initiate); "none" is a valid answer. The review loop is the payoff; the weekly calibration report is the long-term reward that turns journaling into a trainable skill.
