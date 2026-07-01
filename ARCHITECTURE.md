# Butler — Architecture

Butler is a single always-on [Hermes](https://hermes-agent.nousresearch.com/) agent on a home server. It reads Telegram, reasons with a hosted GPT model, and acts by running module scripts inside a write-protected Docker sandbox. Code ships through Git: a laptop pushes to GitHub, and the box continuously pulls `origin/main` as a read-only mirror.

---

## The whole system, one diagram

```
   YOU (phone)                                   EXTERNAL SERVICES (public internet)
   ┌───────────────┐                             ┌───────────────────────────────────────────────────┐
   │ Telegram app  │                             │ OpenAI API · gpt-5.4-mini  ◄── the MODEL (reasoning)│
   └──────┬────────┘                             │ tinyfish MCP  ◄── search / fetch_content / web-auto │
          │ text / voice notes                   │ Google Sheets ◄── the "butler" spreadsheet (CRM)   │
          ▼                                       │ IMAP (Gmail/iCloud) ◄── outreach reply sync        │
   ┌────────────────────┐                         │ Cartesia ◄── TTS (Ronald voice)                    │
   │ Telegram Bot API   │                         └──▲────────────▲───────────────────▲────────────────┘
   │ (cloud; default-   │            (a) HTTPS:       │            │ (b) HTTP MCP       │ (c) the scripts make
   │  deny — only your  │            model + MCP ─────┘            │  calls (gateway)   │  these API calls
   │  user-id is let in)│                                          │                    │
   └──────┬─────────────┘   ════════════════════════════════════════════════════════════════════════════
          │ long-poll       HOME SERVER  "home-server"  · Linux · one OS user: drc · reachable only via Tailscale
          ▼                                          │                                 │
   ┌──────────────────────────────────────────────────────────┐                       │
   │ HERMES GATEWAY — "the brain"                              │                       │
   │ one always-on python process (systemd user service)      │                       │
   │   ┌──────────────────────────────────────────────────┐   │                       │
   │   │ AGENT LOOP: msg+context ─►gpt-5.4-mini─►pick tool  │───┼──(a)(b)───────────────┘
   │   │ ─►run it─►feed result back─►…(≤max_turns)─►reply   │   │
   │   └──────────────────────────────────────────────────┘   │
   │ reads SKILLs from the repo · reads/writes MEMORY in profile
   └───────────────────────────────┬──────────────────────────┘
                                   │ a "tool call" = run a shell command
                                   ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │ DOCKER SANDBOX — "the hands"   (terminal.backend: docker · persistent)         │
   │ every agent shell command `docker exec`s into this one container               │──(c)──►
   │ image python:3.11-slim + host `uv` (mounted) runs the module scripts           │  scripts reach
   │   ┌── mounts (this list IS the agent's write-allowlist) ───────────────────┐   │  Sheets/IMAP/
   │   │  /home/drc/butler        READ-ONLY  ← the code  (★ THE WALL)           │   │  Cartesia
   │   │  profile/state/          read-write ← learned notes + runtime state    │   │
   │   │  crm_google_sa.json      read-only  ← Google Sheets auth               │   │
   │   │  ~/.local/bin/uv         read-only  ← the PEP-723 script runner        │   │
   │   └─────────────────────────────────────────────────────────────────────────┘ │
   │ creds injected via `docker_forward_env`.  write to the repo → "Read-only fs" ✗ │
   └──────────────────────────────────────────────────────────────────────────────┘

   ┌── THE REPO  /home/drc/butler  (git clone of origin/main · READ-ONLY to the agent) ──────────┐
   │ modules/   ← skills, auto-discovered via  config.yaml → skills.external_dirs                 │
   │   tools/ppl-index   tools/cold-outbounds   tools/superforecasting   tools/read-aloud         │
   │   daily/garmin-dashboard   daily/steve-jobs-letter        lib/sheets.py ← shared gspread     │
   │ bootstrap/ ← setup_butler.sh · register_cron.sh · deploy.sh · SOUL.md (canonical persona)    │
   └─────────────────────────────────────────────────────────────────────────────────────────────┘
   ┌── THE PROFILE  ~/.hermes/profiles/butler  (data + secrets · NOT in git · agent-writable) ────┐
   │ .env (secrets)   config.yaml (model/terminal/skills wiring)   SOUL.md (copy of bootstrap's)  │
   │ memories/MEMORY.md (durable memory, auto-loaded)   state.db (sessions, full-text-searchable) │
   │ state/  ← garmin-dashboard/ · steve-jobs-letter/ · learned/   sandboxes/docker/ ← container  │
   └─────────────────────────────────────────────────────────────────────────────────────────────┘
   ┌── CRONS  (systemd timers → Hermes scheduler, mostly "no-agent") ─────────────────────────────┐
   │ steve-jobs-letter · garmin-dashboard · cold-outbounds-nudge · superforecasting (daily+weekly)│
   │ no-agent = run a script, deliver its stdout to Telegram verbatim  (zero GPT tokens)          │
   └─────────────────────────────────────────────────────────────────────────────────────────────┘
   ════════════════════════════════════════════════════════════════════════════════════════════════
   CI/CD — code changes happen ONLY here, never on the box   ▲ git pull --ff-only every 5 min,
   ┌──────────────┐      git push        ┌─────────────────┴──┐  then test gate, then restart
   │ YOUR LAPTOP  │ ───────────────────► │ GitHub origin/main  │  (bootstrap/deploy.sh via systemd timer)
   │ (you / Claude│                      │ (source of truth)   │  the box is a read-only mirror of main
   │  Code edit)  │                      └─────────────────────┘
   └──────────────┘  Butler suggests improvements in chat; it never opens PRs or touches git.
```

**Reading it:** a Telegram message enters the **gateway** (the brain, a host process). The gateway calls the **model** (OpenAI) to reason and may call **MCP** tools (tinyfish) directly over HTTP. When it decides to run a *shell* command, that command executes inside the **docker sandbox** (the hands), where the repo is mounted **read-only** and only the profile's `state/` is writable — so module scripts run and reach Sheets/IMAP/Cartesia, but cannot edit code. Code only changes via **git** (laptop → GitHub → the box's pull-deploy). Brain on the host; hands in a read-only-code sandbox.

---

## 1 — Substrate: box, user, network

- **Box:** a single Linux home server (`home-server`), reachable **only over Tailscale** (a WireGuard mesh VPN) — no public ports.
- **User:** everything runs as one unprivileged user, `drc` (uid 1000, in `sudo`+`docker` groups; sudo is password-gated). One UID for the gateway, the crons, and the deploy — which is exactly why the write-protection had to be a container, not file permissions (DAC can't distinguish same-UID processes).
- **Two roots that are not copies of each other:** the **repo** (`/home/drc/butler`, versioned code) and the **profile** (`~/.hermes/profiles/butler`, live data + secrets, never in git). §9 is built on this distinction.

## 2 — The gateway

**Hermes Agent** (Nous Research, open-source) is the runtime installed on the box — a Python program in a venv. **The model is not installed**; it's a hosted brain Hermes calls over the network. "Butler did X" = Hermes ran the agent loop, which called GPT, which decided X.

- **Gateway = the always-on process.** `hermes-gateway-butler`, a **systemd *user* service** (linger enabled → survives logout/reboot, restarts on crash). It owns the Telegram connection, hands each message to the agent loop, ships the reply. While it's up, Butler is "online."
- **Profile = one agent's entire world in one folder.** Config, secrets, persona, memory, schedule. Hermes can host many profiles (many agents) on one box; we run exactly one. **One profile = one Butler.** Modularity comes from teaching the *one* agent many skills, not from many agents.
- **Model = BYOK GPT.** `gpt-5.4-mini`, reached with our own OpenAI key (`config.yaml: model.provider: custom`, `base_url: api.openai.com/v1`; key in `.env`, never leaves the box). Swapping the brain is a one-line change.
- **SOUL.md** is the persona: a short markdown file loaded at the top of every conversation (calm, concise, "modular butler"). It's also the **one home for global agent policy** — e.g. *skills and code are read-only to you (enforced three ways); learnings go to memory / `state/learned`; the user promotes them via git*. That rule lives here, once, not copy-pasted into each skill (it used to be, and drifted).

## 3 — The agent loop + skills

**agent = model + tools + a loop.** Plain GPT answers once; the loop lets it *act*: call a tool → feed output back → decide the next step → repeat up to `agent.max_turns` (currently 90), then reply.

- **Context window vs rate limit (two different "token" limits):** the *context window* is how much the model can hold per request (hundreds of K); the *rate limit* (TPM, tokens/minute, currently ~4M on our tier) caps how much you can *send* per minute across all calls. One Telegram message = an agent loop of *N* calls, and **each call re-sends the whole accumulated context** (history + tool outputs). So one short message can cost N×(big context) tokens — the multiplier that makes "1 message" expensive. Lean agents fight this with aggressive compaction (`context.engine: compressor`) and by truncating tool output; Butler currently does little of either.
- **Skills (= "modules") and progressive disclosure.** A skill is a folder teaching one capability, centered on `SKILL.md` (name + a one-line *when-to-use* description + how-to). The model always sees the *list* of skill names+descriptions; it pulls a skill's full `SKILL.md` into context **only when the description matches**. ⇒ **the description line is the trigger** — a vague one means the skill silently never fires.
- **Discovery — three sources, no registration:** (1) ~85 Hermes **built-ins**; (2) the profile's own `skills/` dir (agent-installed, `local`, *not* in git → not reproduced by a clone); (3) **our repo's `modules/`**, wired by the single line `skills.external_dirs: [/home/drc/butler/modules]`. That line is the entire bridge between repo and running agent — Hermes reads skills **in place**, no copy.

## 4 — The sandbox

Historically Hermes' terminal ran commands directly on the host as `drc` — a real shell with full access. That let the agent edit its own skill files (it did, and it wedged deploys). Now `terminal.backend: docker`: **every agent shell command runs inside a container instead.**

Mechanics (verified by `docker inspect`):

- Hermes keeps **one persistent container** (`sleep infinity`, image `python:3.11-slim`, name `hermes-<hash>`) and `docker exec`s each command into it. `container_persistent: true` keeps the uv/dep cache warm.
- **`docker_volumes` is the write-allowlist.** Repo `:ro` (the write barrier — a write returns `Read-only file system`); `profile/state/` `:rw` (learned notes + runtime state); `crm_google_sa.json` `:ro`; host `~/.local/bin/uv` `:ro` (the slim image has no uv). Hermes also auto-mounts `modules → /root/.hermes/external_skills/0:ro`, the skill dir, caches, and `/root ← sandboxes/docker/default/home`.
- **Creds reach the container via `docker_forward_env`** (the `.env` var names). Note the dead ends: Hermes **ignores** `docker_extra_args`/`--env-file`, and `shell_init_files` runs host-side; `docker_forward_env` is the one that works.
- **uv** runs the PEP-723 module scripts: it resolves deps (gspread, etc.) into the container cache over the network.
- **Net effect:** the agent reads + executes all code and reaches the network. Memory/sessions are written by the *gateway* (host-side), not the shell, so the sandbox doesn't touch learning.
- **Caveat (load-bearing): the sandbox only governs the *shell*.** Several Hermes tools write host files *outside* the container, bypassing the read-only mount — so the barrier is a **denylist that has to name each one**:
  - **`file`** (read/write/patch host files) → disabled (`agent.disabled_toolsets: [file]`).
  - **`code_execution` / `execute_code`** (run arbitrary in-process Python — the broadest write vector) → disabled (same key). Butler never used it.
  - **`skill_manage`** (create/edit/patch/delete skills, host-side, editing a skill *wherever it lives* — i.e. our repo) → **hook-blocked**. It can't be disabled per-tool: Hermes bundles it with the read tools `skill_view`/`skills_list` in the one `skills` toolset and has no per-tool switch. So a `pre_tool_call` hook (`bootstrap/hooks/block_skill_manage.py`, `matcher: skill_manage`, matched by `fullmatch` so the read tools pass) rejects the call and tells the agent to route the learning to memory / `state/learned` instead.

  This `skill_manage` path is the one that wedged a deploy on **2026-07-01**: mid-enrichment the agent "improved" `ppl-index`, dirtied the repo working tree, and the pull-deploy correctly **skipped** (dirty-tree guard) rather than clobbering — exactly the failure this caveat predicted. A denylist means any *new* host-side write tool needs the same treatment; the fully-robust barrier is filesystem ownership (the repo not writable by the gateway's OS user at all), which isn't in place yet.
- **Gotcha:** because the container is persistent, changing volumes/env/image in `config.yaml` doesn't apply until you remove the stale container (`docker ps -aq --filter ancestor=python:3.11-slim | xargs -r docker rm -f`) and restart.

## 5 — Modules

Six modules + a shared lib. Each is `SKILL.md` (+ optional `scripts/`, `cron/deliver.sh`, `references/`, `module.md`):

| Module | Type | Backed by |
|---|---|---|
| `tools/ppl-index` | interactive | `ppl-index` Sheet tab — people you know; tinyfish-driven auto-enrichment |
| `tools/cold-outbounds` | interactive + cron | `cold-outbounds` tab — outreach log, follow-up nudge, IMAP reply sync |
| `tools/superforecasting` | interactive + cron×2 | `superforecasting` tab — decision journal + calibration |
| `tools/read-aloud` | interactive | Cartesia TTS → Telegram voice notes |
| `daily/garmin-dashboard` | cron + interactive | Garmin API → daily stats + trend log (state in profile) |
| `daily/steve-jobs-letter` | cron (no-agent) | Steve Jobs Archive scrape; never-repeating letter |
| `tools/sheet-backup` | cron (no-agent) | daily CSV snapshot of the Sheet tabs → profile, for the restic→B2 backup; no `SKILL.md` (not agent-invocable) |
| `modules/lib/sheets.py` | — | shared gspread wrapper (header-row-is-schema + retry); imported by the three Sheet modules via a `sys.path` shim |

- **Split by capability, not table.** `ppl-index` (contact store) and `cold-outbounds` (outreach engine: nudges + IMAP sync + reply-status logic) were one `crm` module; splitting them put the heavy email machinery in its own box. Cross-tab "who is X" is composed by the *agent* calling both modules — they stay independent (no shared-find coupling).
- **Script ↔ skill contract.** Scripts print a stable JSON shape to stdout; the skill reasons over it. Scripts run via `uv run …`, reading off disk each invocation — pure, fixture-tested, no LLM. A script with a `--telegram` mode prints the *final* message for the no-agent cron path; default mode prints JSON for the interactive path. One helper, two consumers.
- **Failure is silent-by-design** for no-agent paths: non-zero exit + empty stdout → Hermes sends nothing (better than messaging garbage).

## 6 — Tools beyond the shell: MCP

**tinyfish** is an MCP server (remote, `agent.tinyfish.ai`, OAuth) the *gateway* calls over HTTP — not via the shell sandbox. 17 tools; the enrichment-relevant ones: `search` (free), `fetch_content` (free, markdown), `run_web_automation` (renders/clicks JS- and auth-walled pages like LinkedIn/X — the thing a plain fetch can't do), `batch_create`. Because MCP is gateway-side, the sandbox doesn't affect it.

## 7 — Memory & state

- **Built-in memory:** `memories/MEMORY.md` (+ `USER.md`), always-on, **auto-loaded into context every session** but **capped (~2,200 chars)** with auto-prune — a small, self-maintaining scratchpad for short lessons. (Its smallness is *why* the agent once wrote reference docs into the repo: they didn't fit memory.)
- **Sessions:** `state.db` (SQLite, full-text-searchable past conversations + registered cron rows).
- **Learned notes (longer):** `profile/state/learned/` — agent-writable (it's on the rw mount), off the read-only repo.
- **Module runtime state** lives in the profile too (`state/garmin-dashboard/history.jsonl`, `state/steve-jobs-letter/served.json`), pointed at by `BUTLER_*_STATE` env vars so the repo stays pure read-only code.

Memory is **shared across skills** — one store, many readers (a context-provider module writes; others read).

## 8 — Cron

Hermes' scheduler runs jobs in **agent mode** (wakes the full loop — flexible, costs tokens, model may reword) or **no-agent mode** (runs a script, delivers stdout to Telegram **verbatim** — deterministic, free, tamper-proof). Use no-agent when the output must be exact (the letter), agent when you need judgment. `cron.wrap_response: false` strips Hermes' default `Job ID` + metadata header/footer, so "verbatim" really is verbatim.

**Gotcha:** no-agent crons run with `HOME=<profile>/home` (a sandboxed home), so `~`/`$HOME/.hermes/...` resolve wrong. `cron/deliver.sh` sources the profile `.env` and references the SA key by **absolute path** (`CRM_SA_KEY`) for this reason.

## 9 — Repo vs profile, and the three tiers

The agent reads modules **straight out of the repo checkout** (the `external_dirs` pointer) — so the git working tree on the box *is* the deployment for code. But not everything is a live pointer; which **tier** a file is in tells you what to do after editing:

- **Tier 1 — live-from-repo (zero copy):** `SKILL.md` + `scripts/*.py`. Scripts run via `uv run` → re-read off disk every run; edit → next run has it (a `gateway restart` re-snapshots `SKILL.md` text into the prompt).
- **Tier 2 — copy-on-deploy:** `bootstrap/SOUL.md` → `profile/SOUL.md`, and `cron/deliver.sh` → `profile/scripts/<name>.sh`. Hermes wants these at fixed profile paths; the deploy re-copies them. The copied `deliver.sh` is a thin wrapper that `exec`s back into the repo's Tier-1 Python.
- **Tier 2b — config (merge-on-deploy):** `config.yaml` is profile state, born once from `setup_butler.sh` and otherwise outside git — so a config change used to mean an SSH edit. `bootstrap/config.overrides.yaml` closes that seam: it holds only the keys the repo owns (model, `agent.disabled_toolsets`, the `hooks` block + `hooks_auto_accept`, `cron.wrap_response`), and the deploy deep-merges them onto the live `config.yaml` via `apply_config_overrides.py` (ruamel round-trip — preserves every other key, comment, and Hermes runtime field). Edit the override, push, and the deploy enforces it.
- **Tier 3 — runtime-only (never in git):** `.env`, `config.yaml`, `memories/`, `state.db`, the registered cron rows, `profile/state/*`. Born on the box; the repo can only *reproduce* them (`setup_butler.sh`, `register_cron.sh`).

## 10 — CI/CD: how code goes live

**The box is a read-only mirror of `origin/main`.** Edit on the laptop → commit → `git push`. A systemd timer runs `bootstrap/deploy.sh` every 5 min: `git fetch` → **ff-only** → offline **test gate** (`run_tests.sh`; rollback on failure) → diff-driven activation (re-copy `SOUL.md` / reconcile config overrides / re-register crons / `gateway restart` only as needed) → Telegram ✅/❌/⚠️ ping. **`git push` is the deploy; nobody SSHes in to change code — or config.**

- **The agent can't change prod.** The sandbox makes the box's code read-only to it (it can't edit even locally), and it has no path to Git — it never commits or pushes. Every code change is made by a human on the laptop; the agent's only role is to *suggest* an improvement in chat. (Branch protection on `main` would add a second lock but isn't currently enabled — the sandbox plus the human-only push path are what enforce it today.)
- **Dirty-tree fail-safe:** `deploy.sh` refuses to run over a dirty working tree — it pings you instead of clobbering. So a stray box edit stalls deploys (visibly) rather than silently shipping. Reconcile with `git restore . && git clean -fd`.

## 11 — End to end

**A new contact (the user gives a name, company, and a LinkedIn URL):** gateway → model decides to enrich → calls tinyfish `search`/`fetch_content`/`run_web_automation` (gateway-side HTTP) to pull the profile → decides the fields → runs `contacts.py add` then `update` **in the sandbox** (uv, creds via `docker_forward_env`, writing to the `ppl-index` tab over the network) → replies with what it filled + sources. A repo write anywhere in that chain would be refused.

**The 7am letter (no-agent cron):** systemd keeps the gateway up → at `0 14 * * *` UTC Hermes fires `daily-steve-jobs-letter` in no-agent mode → runs the Tier-2 copied wrapper → `exec`s the Tier-1 `fetch_letter.py --telegram` → it scrapes, picks an unserved letter (state in `profile/state/steve-jobs-letter/served.json`), prints the finished message → Hermes delivers stdout verbatim. **Zero GPT tokens.**

---

## Operational facts

- **Service:** `hermes-gateway-butler` (systemd user service, linger on). Manage: `hermes -p butler gateway {status,restart}`.
- **Access control:** Telegram default-deny — only `TELEGRAM_ALLOWED_USERS` may message it.
- **Autonomy + sandbox:** `approvals.mode: auto` (no per-action approval), but the shell is the read-only-repo docker sandbox, so autonomy can't become a code change.
- **Secrets:** `profile/.env`, mode 600, never committed; forwarded into the sandbox via `terminal.docker_forward_env`.
- **Schedule & DST:** crons run on server time (UTC). `0 14` = 7am PT under PDT, drifts at DST; for DST-proof timing set the server TZ and use local cron times.
- **Backups:** the server runs restic → Backblaze B2 over the profile (sessions, memory, runtime state, secrets — all on the box). The Sheet is the one store that lives off the box, so the `sheet-backup` no-agent cron exports each tab to `state/backups/*.csv`, bringing it into the same backup. restic provides the off-site, encrypted, point-in-time copy.
