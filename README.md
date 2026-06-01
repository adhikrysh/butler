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
| `bootstrap/` | Setup + cron-registration scripts to reproduce Butler on a fresh box. |
| `docs/specs/` | Design specs. One per module/feature. |

## Status

**Live.** Butler runs as a systemd service (`hermes-gateway-butler`, auto-restart + linger) on the home server, on Telegram, locked to a single allowlisted user, powered by OpenAI `gpt-5.4-mini` (BYOK).

- Architecture (start here): [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Design: [`docs/specs/2026-05-31-butler-modular-agent-design.md`](docs/specs/2026-05-31-butler-modular-agent-design.md)
- Plan: [`docs/plans/2026-05-31-butler-foundation-and-letter-module.md`](docs/plans/2026-05-31-butler-foundation-and-letter-module.md)

### Modules
| Module | Type | Schedule | Status |
|--------|------|----------|--------|
| `daily/steve-jobs-letter` | proactive | `0 14 * * *` UTC (7am US Pacific) → Telegram | ✅ live |

> Cron runs on **server time (UTC)**. `0 14 * * *` = 7am PT (PDT). Fixed UTC drifts 1h at DST — for DST-proof timing, set the server TZ to `America/Los_Angeles` and use `0 7 * * *`.
