# Module: jim

- **Type:** interactive (agent-invoked). Reactive coach; proactive check-ins are a
  planned Phase 2 (see the design spec §9).
- **What it does:** an evidence-based personal coach for anything physical. Prescribes
  from Garmin readiness, logs every session, debriefs cardio against per-activity
  Garmin detail, holds goals + the active plan, and computes PRs — reasoning over the
  user's own history, grounded in cited web facts (tinyfish).
- **Sheet:** three tabs of the same `butler` spreadsheet (CRM_SHEET_ID / CRM_SA_KEY),
  each a rendered view, not the source of truth: `Jim Sessions` (one row per logged
  session, with a `jim.py`-rendered summary of its sets), `Jim Programme` (one row per
  stored plan version — grows, doesn't overwrite, so history is kept), and `Jim Goals`
  (one row per goal — grows the same way). No more yellow meta-rows or a single
  `datetime`/`remarks` timeline.
- **Store:** jim owns a typed SQLite layer, `scripts/jimstore.py` (`JimStore`), against
  `butler.db` — NOT the generic `lib/store.py`. Tables: `jim_sessions` (one row per
  logged session) + `jim_sets` (one row per set, `session_id` FK, per-set `weight`/
  `reps`/`e1rm` — the per-set granularity the old free-text `remarks` couldn't give),
  plus `jim_programme` (one row per plan version, `active` flag) and `jim_goals` (one
  row per goal, `status`). The DB is the source of truth; the 3 Sheet tabs above are a
  rendered projection. `jim.py resync` rebuilds all three tabs from the DB on drift.
- **Tools:** `scripts/jim.py` CLI — `log / plan / goal / goal-update / current /
  progress / prs / dump / resync` — over `jimstore.py` (typed SQLite + Sheet
  projection), `lib/garmin.py` (shared Garmin client), and `scripts/jimcore.py` (pure:
  `e1rm`, `exercise_metrics`, `session_volume`, `compute_prs`, `progression`,
  `weekly_adherence`, `render_summary`, `render_plan_text`, `latest_active`,
  `active_goals`). The agent is responsible for structuring freeform workout reports
  into `exercises[].sets[]` before calling `log` — `jim.py` itself does no natural-
  language parsing.
- **Garmin sync (reactive freshness):** cardio logs enrich from the matching same-day
  Garmin activity. Sync is best-effort and NEVER blocks a write; jim fires a
  **jim-scoped** trigger `JIM_SYNC_CMD` (Pushcut → iPhone opens Garmin Connect → FR955
  BLE-syncs), polls briefly, then back-enriches later if needed. The shared daily
  garmin cron is untouched (it keys off `GARMIN_SYNC_CMD`, still unset). See spec §5b.
- **Tests:** `tests/test_jimcore.py` (pure) + `tests/test_jimstore.py` (SQLite layer). Run:
  `cd modules/tools/jim && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q`.
  Wired into `bootstrap/run_tests.sh`.
- **Env (forwarded into the docker sandbox via `docker_forward_env`):** `JIM_SYNC_CMD`,
  `BUTLER_DB_PATH`, plus the shared `CRM_SHEET_ID`/`CRM_SA_KEY`/`GARMIN_EMAIL`/
  `GARMIN_PASSWORD`. See `bootstrap/setup_butler.sh`. (`BUTLER_JIM_STATE` is now unused
  — the jsonl mirror was retired.)
- **Memory:** none. SQLite (`butler.db`) is the durable store; no main-agent/memory changes.
