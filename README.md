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

Design phase. See [`docs/specs/2026-05-31-butler-modular-agent-design.md`](docs/specs/2026-05-31-butler-modular-agent-design.md).

First module: **Daily Steve Jobs letter** (07:00 → Telegram).
