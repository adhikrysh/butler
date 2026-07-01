# Module: learnings

- **Type:** interactive (agent logs + marks reviewed) + proactive (no-agent weekly digest cron).
- **What it does:** the continual-learning loop. The agent cannot edit its own skills (`skill_manage` is hook-blocked), so it logs skill-improvement ideas here; a weekly digest surfaces the pending ones; the user promotes the good ones into a skill by hand, via git. Severity gates attention (high → inline + digest; med → digest; low → logged only), never action.
- **Store:** `state/learned/learnings.jsonl` (append-only, on the profile's rw mount — never the repo). Record: `{id, ts, skill, insight, why, importance, status}`; `importance ∈ {low,med,high}`, `status ∈ {new,promoted,dismissed}`. Path from `BUTLER_LEARNED_STATE`, default the absolute profile path (same inside the sandbox).
- **Tools:** `scripts/learn.py` CLI — `add / pending / list / review / digest` — over `scripts/learncore.py` (pure: normalize, dedup, pending filter, review, digest formatting). Stdlib only, no Sheets, no deps.
- **Cron (no-agent):** `cron/deliver.sh` → `learn.py digest` (`0 4 * * 1` UTC, Sun ~9pm PT — the weekly review digest; empty output → no message). Registered in `bootstrap/register_cron.sh`.
- **Tests:** `tests/test_learncore.py` (pure functions) + `tests/test_learn.py` (CLI round-trip on a temp store). Run: `cd modules/tools/learnings && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q`. Wired into `bootstrap/run_tests.sh`.
- **Design:** the positive half of the read-only-skills change — the hook (`bootstrap/hooks/block_skill_manage.py`) removes the bad path (self-editing); this module builds the good one (capture → surface → human-promote). Capture is frictionless; promotion is deliberate and git-gated.
