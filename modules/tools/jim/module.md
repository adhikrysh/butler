# Module: jim

- **Type:** interactive (agent-invoked). Reactive coach; proactive check-ins are a
  planned Phase 2 (see the design spec §9).
- **What it does:** an evidence-based personal coach for anything physical. Prescribes
  from Garmin readiness, logs every session, debriefs cardio against per-activity
  Garmin detail, holds goals + the active plan, and computes PRs — reasoning over the
  user's own history, grounded in cited web facts (tinyfish).
- **Sheet:** the `Jim` tab of the same `butler` spreadsheet (CRM_SHEET_ID / CRM_SA_KEY).
  One append-only timeline. Columns: `datetime` (PK), `type`, `title`, `duration_min`,
  `distance_km`, `avg_hr`, `calories`, `rpe`, `garmin_activity_id`, `remarks`. Session
  rows vs yellow meta-rows (`goal`/`plan`/`note`); latest `plan` row = active plan,
  latest `goal` rows = current goals. Header-row-is-schema. Auto-created via
  `Sheet.ensure_tab`. Mirrored to `state/jim/log.jsonl` (BUTLER_JIM_STATE).
- **Tools:** `scripts/jim.py` CLI — `log / note / current / prs / dump` — over
  `lib/sheets.py` (gspread wrapper + `ensure_tab`/`append_colored`), `lib/garmin.py`
  (shared Garmin client), and `scripts/jimcore.py` (pure: strength parsing, e1RM, PR
  computation, latest-by-type, recent sessions).
- **Garmin sync (reactive freshness):** cardio logs enrich from the matching same-day
  Garmin activity. Sync is best-effort and NEVER blocks a write; jim fires a
  **jim-scoped** trigger `JIM_SYNC_CMD` (Pushcut → iPhone opens Garmin Connect → FR955
  BLE-syncs), polls briefly, then back-enriches later if needed. The shared daily
  garmin cron is untouched (it keys off `GARMIN_SYNC_CMD`, still unset). See spec §5b.
- **Tests:** `tests/test_jimcore.py` (pure). Run:
  `cd modules/tools/jim && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q`.
  Wired into `bootstrap/run_tests.sh`.
- **Env (forwarded into the docker sandbox via `docker_forward_env`):** `JIM_SYNC_CMD`,
  `BUTLER_JIM_STATE`, plus the shared `CRM_SHEET_ID`/`CRM_SA_KEY`/`GARMIN_EMAIL`/
  `GARMIN_PASSWORD`. See `bootstrap/setup_butler.sh`.
- **Memory:** none. The sheet is the durable store; no main-agent/memory changes.
