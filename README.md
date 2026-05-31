# Butler

A single self-hosted [Hermes Agent](https://hermes-agent.nousresearch.com/) on Telegram that grows a modular set of personal use cases over time.

- **One agent** (`butler` Hermes profile) — not many. Modularity lives *inside* it.
- **Each use case = one git-versioned skill** in [`modules/`](modules/), optionally with a cron schedule and a helper script.
- **Shared memory** is the cross-module context layer (e.g. Garmin data informing the gym & health modules).

## Layout

| Path | Purpose |
|------|---------|
| `modules/` | The modules (skills). Wired into Hermes via `config.yaml` → `skills.external_dirs`. Source of truth. |
| `bootstrap/` | Setup + cron-registration scripts to reproduce Butler on a fresh box. |
| `docs/specs/` | Design specs. One per module/feature. |

## Status

**Live.** Butler runs as a systemd service (`hermes-gateway-butler`, auto-restart + linger) on the home server, on Telegram, locked to a single allowlisted user, powered by OpenAI `gpt-5.4-mini` (BYOK).

- Design: [`docs/specs/2026-05-31-butler-modular-agent-design.md`](docs/specs/2026-05-31-butler-modular-agent-design.md)
- Plan: [`docs/plans/2026-05-31-butler-foundation-and-letter-module.md`](docs/plans/2026-05-31-butler-foundation-and-letter-module.md)

### Modules
| Module | Type | Schedule | Status |
|--------|------|----------|--------|
| `daily/steve-jobs-letter` | proactive | `0 7 * * *` → Telegram | ✅ live |

> Schedule is in the **server timezone** (currently UTC). Adjust the cron hour for your local 07:00.
