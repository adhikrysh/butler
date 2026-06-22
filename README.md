# Butler

A single self-hosted [Hermes Agent](https://hermes-agent.nousresearch.com/) on Telegram that grows a modular set of personal use cases over time.

- **One agent** (`butler` Hermes profile) — not many. Modularity lives *inside* it.
- **Each use case = one git-versioned skill** in [`modules/`](modules/), optionally with a cron schedule and a helper script.
- **Shared memory** is the cross-module context layer (e.g. Garmin data informing the gym & health modules).

## Layout

| Path | Purpose |
|------|---------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **Start here.** How Hermes, deployment, the module structure, and where-everything-lives actually work — from first principles. |
| `modules/` | The modules (skills). Wired into Hermes via `config.yaml` → `skills.external_dirs`. Source of truth. |
| `bootstrap/` | Setup, cron-registration, and self-deploy scripts to reproduce + auto-deploy Butler on a fresh box. |
| `docs/` | Design specs & plans — kept **locally**, git-ignored (not tracked in this repo). |

## Status

**Live.** Butler runs as a systemd service (`hermes-gateway-butler`, auto-restart + linger) on the home server, on Telegram, locked to a single allowlisted user, powered by OpenAI `gpt-5.4-mini` (BYOK).

- Architecture (start here): [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Design specs & plans live **locally** under `docs/` (git-ignored).

### Modules
| Module | Type | Schedule | Status |
|--------|------|----------|--------|
| `daily/steve-jobs-letter` | proactive | `0 14 * * *` UTC (7am US Pacific) → Telegram | ✅ live |
| `daily/garmin-dashboard` | proactive + interactive | `0 4 * * *` UTC (9pm US Pacific) → Telegram | ✅ live |
| `tools/read-aloud` | interactive (on-demand) | — (no cron) | ✅ live |

> Cron runs on **server time (UTC)**. `0 14 * * *` = 7am PT (PDT). Fixed UTC drifts 1h at DST — for DST-proof timing, set the server TZ to `America/Los_Angeles` and use `0 7 * * *`.

## Deployment — pull-based self-deploy

The box runs a **read-only mirror of `origin/main`**: you edit on the laptop, commit, and push; the box pulls and deploys *itself*. Nobody SSHes in. A NAT'd home server should pull, not be pushed to — it needs only outbound HTTPS to GitHub, no inbound access, no stored creds.

- A **systemd timer** wakes every **5 min** and runs `bootstrap/deploy.sh`.
- `deploy.sh` fast-forwards to `origin/main`, runs the offline test suite (the CI gate — rolling back on failure), then — driven by the diff — re-copies `SOUL.md`, re-runs `register_cron.sh`, and/or restarts the gateway **only** for the changes that need it.
- It pings Telegram `✅` / `❌` / `⚠️` so every deploy is visible.

> ✅ **Live since 2026-06-22.** A systemd user timer runs `bootstrap/deploy.sh` every 5 min on the box: fast-forward `origin/main` → offline test gate (rollback on fail) → diff-driven restart / cron re-register → Telegram ✅/❌/⚠️. Push to `main` and the box converges within ~5 min, no SSH. One-time setup: `bootstrap/install_deploy.sh` on the box. See `ARCHITECTURE.md` Part 6.
