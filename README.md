# Butler

Self-hosted personal agent on Telegram: one [Hermes](https://hermes-agent.nousresearch.com/) profile (`butler`, GPT-5.4-mini, BYOK) running as a systemd service on a home server. Capabilities are modular skills under `modules/`.

## Architecture

- One profile, one gateway, one allowlisted Telegram user. Modules are wired in through `config.yaml → skills.external_dirs` and read in place — no copy step.
- A module is `SKILL.md` (trigger + instructions) plus optional `scripts/` and a `cron/deliver.sh`. Modules are a small subset of the agent's skills — Hermes also ships ~85 built-in skills (`hermes -p butler skills list`).
- Cron jobs run in no-agent mode (script stdout delivered to Telegram verbatim — `cron.wrap_response: false`, so no Job-ID/metadata header or footer) or agent mode.
- Mutable state lives in the **profile** (`memories/`, `state.db`, `state/`), never in the repo — the repo is pure, versioned code.
- **Write-protection sandbox (the safety model).** The agent's shell runs inside a docker container (`terminal.backend: docker`) that mounts the repo **read-only** and the profile `state/` read-write. Butler reads and *executes* all code but **cannot modify a skill, script, or module** — a write returns `Read-only file system`. (The sandbox only governs the shell, so Hermes' host-side `file` toolset is disabled too — `agent.disabled_toolsets: [file]` — forcing every file write through it.) Code changes go only through git (laptop push → pull-deploy); the agent is sandboxed out of editing code and can only *suggest* improvements in chat. Continual learning still flows: short lessons → `memories/MEMORY.md` (auto-loaded, ~2.2k-char cap), longer notes → the profile's `state/learned/`.
- Internals + deploy tiers: [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Layout

| Path | Contents |
|------|----------|
| `modules/` | Skills — source of truth, auto-discovered via `external_dirs` |
| `modules/lib/` | Shared library (gspread Sheets wrapper) imported by the sheet-backed modules |
| `bootstrap/` | Profile setup, cron registration, self-deploy |
| `ARCHITECTURE.md` | System internals + deployment model |

## Modules

| Module | Type | Schedule (UTC) | Function |
|--------|------|----------------|----------|
| `daily/steve-jobs-letter` | proactive, no-agent | `0 14 * * *` | Non-repeating letter from the Steve Jobs Archive |
| `daily/garmin-dashboard` | proactive (no-agent) + interactive | `0 4 * * *` | Garmin health pull via API (sync-gated); daily summary; curated trend log in `state/history.jsonl` |
| `tools/read-aloud` | interactive | — | URL/text → Cartesia TTS (Ronald) → chunked Telegram voice notes |
| `tools/ppl-index` | interactive | — | People you know (`ppl-index` tab): log/find contacts; auto-enriches each by finding their LinkedIn/X/email itself via the tinyfish MCP (search/fetch + web automation for walled pages; sources noted, guesses flagged) |
| `tools/cold-outbounds` | interactive + proactive (no-agent) | `0 4 * * *` | Outreach engine (`cold-outbounds` tab): log outreach, drop/snooze, follow-up nudge digest. IMAP email sync in progress |
| `tools/superforecasting` | interactive + proactive (no-agent) | `0 3 * * *` daily · `30 3 * * 1` weekly | Decision journal / calibration (`superforecasting` tab): log decisions with a probability + expected outcome, daily check-in, review resurfacing, weekly calibration report (stated confidence vs actual hit-rate) |
| `tools/sheet-backup` | proactive, no-agent | `0 8 * * *` | Daily CSV snapshot of every Sheet tab into the profile, captured by the server's restic→B2 backup |

Crons run on server time (UTC): `0 14` = 7am PT, `0 4` = 9pm PT, `0 3` = 8pm PT, `0 8` = 1am PT (under PDT), +1h drift at DST.

## Deployment

Pull-based. The box is a read-only mirror of `origin/main`; a systemd user timer runs `bootstrap/deploy.sh` every 5 minutes: fast-forward, run the offline test gate (rollback on failure), then diff-driven activation — re-copy `SOUL.md`, reconcile config overrides, re-register crons, and restart the gateway only as the change requires — with a Telegram status ping. `git push` is the deploy — for code *and* config.

Fresh box:

```bash
# install Hermes, then:
bootstrap/setup_butler.sh                  # profile config + secrets (prompted)
TG_USER_ID=<id> bootstrap/register_cron.sh # register schedules
bootstrap/install_deploy.sh                # enable the self-deploy timer
```

## Operations

- **Service:** `hermes-gateway-butler` (systemd user service, linger enabled). Manage with `hermes -p butler gateway {status,restart}`.
- **Access:** Telegram default-deny — only `TELEGRAM_ALLOWED_USERS` may message it.
- **Autonomy + sandbox:** `approvals.mode: auto` — Butler runs tools without per-action approval, but its shell is sandboxed (repo mounted read-only — see Architecture), so full autonomy still can't become a code change. Telegram is default-deny on top.
- **Secrets:** profile `.env`, mode `600`, never committed; forwarded into the sandbox via `terminal.docker_forward_env`. The agent's shell runs in a read-only-repo docker sandbox, not a raw host shell.
- **Tests:** `bootstrap/run_tests.sh` — offline, fixture-based; the deploy gate runs it.
- **Backups:** the server runs restic → Backblaze B2 over the profile (sessions, memory, runtime state, secrets). The `sheet-backup` cron adds the Google Sheet tabs as CSV, so the only app data living off the box is captured too.
