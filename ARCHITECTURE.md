# Butler — Architecture

Butler is one program on a home server that reads your Telegram messages, thinks with
GPT, and can run code on that server. Everything below is detail about how those three
things are wired — and, just as important, **where each piece lives and how an edit you
make becomes live behavior.**

Read it top to bottom once. By the end you'll know how the agent works, how deployment
works, how a module is structured, and where every file sits.

---

## The whole system in one picture

```
                          YOU, on Telegram
                                │  "today's letter"
                                ▼
              ┌───────────────────────────────────┐
              │      hermes-gateway-butler         │   ← always-on process
              │  the GATEWAY — the door to Telegram│     (a systemd service)
              └───────────────────────────────────┘
                                │  hands the message to…
                                ▼
              ┌───────────────────────────────────┐
              │           the AGENT loop           │   GPT decides what to do
              │  read message → pick a SKILL →     │   and calls tools to do it
              │  run it → reply                    │
              └───────────────────────────────────┘
                   │              │              │
            reads  │       reads/ │        runs  │  (real shell on the box)
          SKILL.md │       writes │      scripts │
                   ▼              ▼              ▼
            ┌──────────┐   ┌──────────┐   ┌──────────────┐
            │  SKILLS  │   │  MEMORY  │   │  the box's   │
            │(modules) │   │ (shared) │   │  filesystem  │
            └──────────┘   └──────────┘   └──────────────┘
```

Three moving parts, and that's really all there is:

- **The door** — the *gateway*, an always-on process that connects Telegram to the agent.
- **The brain** — the *agent loop*, GPT deciding what to do and calling tools to do it.
- **The hands** — a *real shell* on the server, which is how Butler runs scripts and touches files.

Everything else — persona, skills, memory, schedules — just shapes how those three behave.

---

## Part 1 — What is actually running

### An "agent" is a model in a loop

Plain GPT answers once and stops. An **agent** wraps the model in a loop: you give it a
goal, it can call **tools** (here, a shell on the box), the tool's output is fed back in,
and the model decides the next step — repeat until the task is done. So:

> **agent = a language model + tools + a loop around them.**

The brain only *thinks*; the loop is what lets it *act*.

### Hermes runs the loop

The loop is run by **Hermes** (Hermes Agent, open-source, from Nous Research — version
`v0.15.1` here). Hermes is the program that's actually installed on the server. GPT is not
installed; it's a brain Hermes calls over the network. When you read "Butler did X," it
means *Hermes ran the agent loop, which called GPT, which decided to do X.*

### The gateway is the always-on door

The agent loop has to be reachable, 24/7, even when you're asleep. The **gateway** is the
long-running process that listens on Telegram, hands each incoming message to the agent
loop, and ships the reply back. It's named `hermes-gateway-butler` and is run by
**systemd** (Linux's service manager) so it restarts on crash and starts on boot. While
that process is up, Butler is "online." (Right now it's been up ~17h, set to survive
reboots.)

### A "profile" is one agent's entire world in one folder

Everything that makes Butler *Butler* — its config, secrets, persona, memory, schedule —
lives in a single folder called a **profile**:

```
~/.hermes/profiles/butler/
```

Hermes can host several profiles (several different agents) on one machine, each fully
isolated in its own folder. We run exactly one, `butler`. Hermes ties one gateway to one
identity, so **one profile = one Butler.** This is the central design decision:

> Modularity does **not** come from running many agents. It comes from teaching the **one**
> agent many skills.

### The brain is BYOK GPT

The model is **GPT (`gpt-5.4-mini`)**, reached over the network with our own OpenAI API key
— "BYOK," bring your own key. The key lives in the profile's `.env` and never leaves the
box. `config.yaml` names the model and points at OpenAI's API:

```yaml
model:
  default: "gpt-5.4-mini"
  provider: "custom"
  base_url: "https://api.openai.com/v1"
```

Swapping in a stronger brain later (say, for a coaching module) is a one-line change here.

### SOUL.md is the persona

`SOUL.md` is a short markdown file loaded at the start of every conversation that tells the
model *who it is*: calm, concise, a "modular butler," Telegram-friendly, careful with the
real shell it's been given. It's instructions, not code — the difference between GPT and
*Butler* is mostly this file plus the skills.

### Memory is what persists

By default an LLM forgets everything between messages. **Memory** is the set of files and
the database the agent can read and write that survive across conversations:

- `memories/` — curated notes the agent keeps.
- `state.db` — a SQLite database holding past sessions, searchable with full-text search.

Memory is **shared across all skills.** That's the whole point: a future Garmin module can
write your health data into memory, and a separate gym-coach module can read it. One
memory, many readers — that's how independent modules end up sharing context.

---

## Part 2 — Skills are the unit of capability (a "module" is a skill)

This is the most important concept, so slow down here.

A **skill** is a folder that teaches the agent *one* capability. In this repo we call a
skill a **module** — same thing, different word. A skill is mostly one markdown file,
`SKILL.md`, containing:

- a **name**,
- a **one-line description of when to use it**, and
- **instructions** for how to do it.

Optionally it ships helper **scripts** and **reference** files alongside.

### Progressive disclosure — why the description line is load-bearing

The model can only consider so much text at once (its **context window** is finite).
Pasting the full instructions of twenty skills into every conversation would crowd out the
actual conversation. So Hermes uses **progressive disclosure**:

- The agent **always** sees the short list of skill *names + descriptions*.
- It pulls a skill's **full `SKILL.md`** into context **only when that skill looks
  relevant** to what you asked.

Consequence: the **description line is the trigger.** Write it well ("use when adhi asks
for today's letter…") or the skill silently never fires. This is the single most common way
a new module fails to work — a vague description.

### Two ways a skill fires

1. **Slash command:** you type `/steve-jobs-letter`.
2. **Natural language:** you say "today's letter" and the description matches.

Both routes run the same skill.

### How Butler finds skills — `external_dirs`

Hermes **auto-discovers** skills from disk — drop a folder in the right place and it
appears, no registration step. There are **two** such places, and the distinction is the
crux of this whole document:

1. **The profile's own `skills/` dir** (`~/.hermes/profiles/butler/skills/`) — Hermes'
   built-ins and any skill the agent writes *for itself*. We mostly leave this alone.
2. **Our modules,** which live in **this git repo**, wired in by one line in `config.yaml`:

   ```yaml
   skills:
     external_dirs:
       - /home/drc/butler/modules
   ```

That one line is the entire bridge between "the repo" and "the running agent." It tells
Hermes: *also read skills straight out of that repo folder.* **No copy is made** — the
agent reads the files in place. Hold onto that fact; Part 5 is built on it.

---

## Part 3 — Cron does things on a schedule

A **cron job** is "run this thing at this time." Hermes has its own scheduler that can
deliver results to Telegram. It runs in one of **two modes**, and the difference is a real
design lever:

- **Agent mode (the default):** at the scheduled time, the full agent loop wakes up, reads
  a prompt, thinks with GPT, and acts. Flexible, but it costs tokens and the model could
  reword or shorten the output.
- **No-agent mode (`--no-agent`):** at the scheduled time, Hermes just runs a **script** and
  delivers the script's **stdout to Telegram verbatim** — *no LLM call at all.*

The daily letter uses **no-agent mode** on purpose. A letter should arrive exactly as
written. Routing it through a model would mean tokens, latency, and the risk the model
truncates or "improves" the text. A script that prints the final message and hands it
straight to Telegram is deterministic, free, and tamper-proof. **Reach for no-agent mode
whenever the output should be exact; reach for agent mode when you need judgment.**

---

## Part 4 — A module up close

Here's the one module we have, and the reusable shape every future module copies:

```
modules/daily/steve-jobs-letter/
├── SKILL.md                 # required: name + description (the trigger) + how-to
├── module.md                # our notes: type, schedule, the exact cron command, tests
├── scripts/
│   └── fetch_letter.py      # deterministic helper — does the real work, no LLM
├── cron/
│   └── deliver.sh           # the no-agent entrypoint the scheduler runs
├── tests/
│   ├── test_fetch_letter.py # offline tests…
│   └── fixtures/*.html      # …against saved copies of the website (ground truth)
└── state/
    └── served.json          # runtime memory of which letters were sent (gitignored)
```

### The script ↔ skill contract

The Python script and the skill talk through a **stable JSON shape**. `fetch_letter.py`
prints exactly:

```json
{ "id": "...", "title": "...", "author": "...", "date": "...", "url": "...", "text": "..." }
```

As long as those field names hold, the skill and the script can change independently. This
is the same "deterministic helper does the work, the agent just frames it" pattern that the
future Garmin and email modules will reuse.

### Two execution paths from one module

The same module serves both a human and a schedule:

- **Interactive (you ask in chat):** the agent is already in the loop. `SKILL.md` tells it
  to run `fetch_letter.py`, read the JSON, write a warm one-liner, and send the letter.
- **Scheduled (7am push):** **no agent.** `cron/deliver.sh` runs
  `fetch_letter.py --telegram`, which prints the *final* message; Hermes sends that stdout
  verbatim.

Notice the script has two output modes — JSON for the agent path, a finished message for
the `--telegram` path. One helper, two consumers.

### Failure is silent-by-design

If the website changes or the network drops, the script exits non-zero with a one-line
reason and **empty stdout**. In no-agent mode, empty stdout means Hermes sends nothing —
Butler stays quiet for the day rather than messaging you garbage. The interactive path
instead tells you it couldn't fetch the letter. Never invent a letter.

---

## Part 5 — Where everything lives (the part most worth understanding)

There are **two places**, and they are not two copies of the same thing.

```
   THE REPO  (git-versioned, the source of truth)        THE PROFILE  (live runtime, NOT in git)
   /home/drc/butler/                                      ~/.hermes/profiles/butler/
   ─────────────────────────                              ──────────────────────────────────
   modules/                                               config.yaml   ← the external_dirs line
     steve-jobs-letter/                                   .env          ← secrets (keys, token)
       SKILL.md         ◄───── external_dirs wire ──────  SOUL.md       ← a COPY of bootstrap/SOUL.md
       scripts/*.py        (agent reads skills + runs     scripts/      ← a COPY of cron/deliver.sh
       cron/deliver.sh      scripts straight from here)   cron + state.db ← the registered schedule
       state/served.json ◄── runtime state (gitignored)   memories/     ← shared memory
   bootstrap/SOUL.md ─────── copied on setup ──────────►  sessions/     ← past conversations (FTS)
   bootstrap/*.sh                                         skills/       ← Hermes' OWN built-in skills
   docs/, README, ARCHITECTURE.md                         logs/, gateway.pid, …
```

- **The repo** is what you *version*. It's a normal git checkout, mirrored to GitHub and
  cloned on both the server and the laptop.
- **The profile** is what the agent *is* — its live state. It is **not** in git. Secrets,
  memory, and the registered schedule are born here and live only here.

The agent reads your modules **directly out of the repo checkout** via the `external_dirs`
line. So there is no separate "deploy" of your code: **the git working tree on the box *is*
the deployment.**

But — not everything works by that live pointer. There are **three deployment tiers**, and
knowing which tier a file is in tells you *exactly* what to do after editing it.

### Tier 1 — Live-from-repo (a pointer, zero copy)

`SKILL.md` files and `scripts/*.py`. The agent reads them in place. The Python is *extra*
live: it's invoked as `uv run /…/fetch_letter.py`, which reads the file off disk on **every
run**. **Edit a script → the next run already has the change. No restart, nothing.**

### Tier 2 — Copy-on-deploy (the repo is canonical; the profile holds a stale copy)

`SOUL.md` and the cron wrapper `deliver.sh`. Hermes insists on finding these at **fixed
profile paths** — the persona at `profile/SOUL.md`, and `cron --script <name>` resolves only
under `profile/scripts/`. It won't follow a pointer into your repo. So the bootstrap scripts
**copy** them out:

- `bootstrap/setup_butler.sh`: copies `bootstrap/SOUL.md` → `profile/SOUL.md`
- `bootstrap/register_cron.sh`: copies `cron/deliver.sh` → `profile/scripts/steve_jobs_letter.sh`

The mechanism forces the consequence: **edit `bootstrap/SOUL.md` in the repo and nothing
changes until you re-copy it.** The profile holds a photograph that goes stale the moment
you edit the original. (Clever detail: the copied `deliver.sh` is a *thin* wrapper that
points back at the repo's Python, so only the tiny shell stub is duplicated; the real logic
stays Tier 1.)

### Tier 3 — Runtime-only state (never in the repo at all)

The registered cron job, the `.env` secrets, the shared memory (`memories/`, `state.db`),
and `served.json`. These are **born on the box.** The repo can only *reproduce* them —
`register_cron.sh` re-creates the schedule, `setup_butler.sh` prompts for the secrets — but
the live values exist nowhere in git. The schedule, for instance, is a row inside
`state.db`; the repo only remembers the *command* that creates it.

### One trap worth memorizing

`served.json` sits at `modules/daily/steve-jobs-letter/state/served.json` — physically
**inside** the repo tree, but **gitignored** (`.gitignore` has `**/state/`). So a Tier-3
runtime file lives inside a Tier-1 folder. Don't let the path fool you: that file belongs to
the box, not the repo.

### The full map

| Path | Tier | What it is |
|------|------|------------|
| `modules/**/SKILL.md` | 1 live | The skill the agent reads (its trigger + how-to) |
| `modules/**/scripts/*.py` | 1 live | Deterministic helpers, run fresh each time |
| `modules/**/module.md` | — | Our notes (type, schedule, cron command, tests). Docs only |
| `modules/**/cron/deliver.sh` | 2 copy | No-agent entrypoint; copied into the profile |
| `modules/**/state/*.json` | 3 state | Runtime state, gitignored, lives on the box |
| `bootstrap/SOUL.md` | 2 copy | Canonical persona; copied to `profile/SOUL.md` |
| `bootstrap/setup_butler.sh` | — | Recreates the profile on a fresh box |
| `bootstrap/register_cron.sh` | — | Recreates all schedules from the repo |
| `profile/config.yaml` | 3 state | Model, terminal, and the `external_dirs` wire |
| `profile/.env` | 3 state | Secrets: OpenAI key, Telegram token, allowlist |
| `profile/state.db` | 3 state | Sessions (FTS) + registered cron jobs |

---

## Part 6 — How a change goes live (deployment)

**The box is a deploy-only mirror of `origin/main`.** Edit on the laptop, commit, push.
A systemd timer (`butler-deploy.timer`) runs `bootstrap/deploy.sh` on the box every 5 min:
it fast-forwards to `origin/main`, runs the offline test gate (rolling back on failure),
then activates only what the diff touched, and pings Telegram ✅/❌/⚠️. So a `git push`
**is** the deploy — nobody SSHes in. Do **not** hand-edit the box: `deploy.sh` refuses to run
over a dirty tree (it pings you instead of clobbering), so a stray box edit just stalls
deploys until you reconcile it.

`deploy.sh` encodes the table below — the "to make it live, you…" column is now what it does
for you automatically, keyed off `git diff`:

| You changed… | To make it live, you… | Why |
|---|---|---|
| a `scripts/*.py` | do nothing | run fresh via `uv run` every time |
| a `SKILL.md` (text or frontmatter) | `gateway restart` | skills are snapshotted into the prompt at start |
| added a **new** module folder | `gateway restart` | discovery happens at start |
| `bootstrap/SOUL.md` | re-copy it, then `gateway restart` | Tier 2: the profile holds a copy |
| `cron/deliver.sh` or a schedule | re-run `register_cron.sh` | Tier 2 copy + Tier 3 state |
| a secret in `.env` | `gateway restart` | loaded at start |

Restart command:

```bash
hermes -p butler gateway restart      # ('butler …' is the same thing if the alias is set)
```

---

## Part 7 — End to end: the 7am letter

Every hop, no magic:

1. **systemd** keeps `hermes-gateway-butler` running (enabled, survives reboot).
2. At `0 14 * * *` UTC (= 7am US Pacific), Hermes' scheduler fires the job
   `daily-steve-jobs-letter` in **no-agent** mode.
3. It runs `profile/scripts/steve_jobs_letter.sh` — the Tier-2 **copy** — which `exec`s
   `uv run /…/modules/daily/steve-jobs-letter/scripts/fetch_letter.py --telegram` — the
   Tier-1 **live** script in the repo.
4. The script scrapes the archive, picks a letter **not** already in `state/served.json`
   (resetting once all are used), appends its choice to that file (Tier-3 state), and prints
   the finished message to **stdout**.
5. Because the job is `--no-agent`, Hermes delivers that stdout **verbatim** to
   `telegram:<your-id>`. **Zero GPT tokens** — no model ever touches the letter.

That's the whole system exercising every part: service → scheduler → copied wrapper → live
script → runtime state → Telegram.

---

## Part 8 — Adding a new module (the recipe)

Because modules are read live from the repo and share one memory, adding a use case touches
**nothing else.** The steps:

1. **Copy the shape.** `modules/<category>/<name>/` with a `SKILL.md` (name + a sharp
   *when-to-use* description + how-to). Add `scripts/` if it needs deterministic work,
   `module.md` for your notes.
2. **Pick the module type:**
   - **Interactive** — skill only; the agent runs it when you ask. (e.g. gym coach)
   - **Proactive** — add `cron/deliver.sh` and a line in `register_cron.sh`. Use
     **no-agent** if the output should be exact, **agent** if it needs judgment.
   - **Context-provider** — a script that refreshes data into shared **memory** for other
     modules to read. (e.g. Garmin)
3. **Test in three rungs:** the script alone (offline, against saved fixtures) → the skill
   from chat → the schedule with a near-future one-shot before the real time.
4. **Make it live:** commit, push, `git pull` on the box if you edited elsewhere, then
   `gateway restart`. For a scheduled module, also run `register_cron.sh`.

That small, fixed surface area — drop a folder, restart — is the entire reason this design
lets capabilities grow one at a time without disturbing the ones already working.

---

## Operational facts

- **Service:** `hermes-gateway-butler` (systemd *user* service), `enabled` + linger on, so
  it runs 24/7 across logout and reboot. Manage with `hermes -p butler gateway {status,restart}`.
- **Access control:** Telegram is **default-deny** — only the allowlisted user ID
  (`TELEGRAM_ALLOWED_USERS` in `.env`) can talk to Butler.
- **Secrets:** only in `profile/.env`, mode `600`, never committed.
- **No OS sandbox:** Butler has a **real shell with full access** to the server user's
  files. That's deliberate and fine for a single-user home box — but it's the reason
  `SOUL.md` tells it to act carefully, and the reason to think before giving a module
  destructive powers.
- **Schedule & DST:** cron runs on **server time (UTC)**. `0 14 * * *` = 7am Pacific during
  PDT and drifts an hour at DST. For DST-proof timing, set the server TZ to
  `America/Los_Angeles` and use `0 7 * * *`.

---

## See also

- `docs/specs/2026-05-31-butler-modular-agent-design.md` — *why* it's designed this way (the
  decisions and trade-offs).
- `docs/plans/2026-05-31-butler-foundation-and-letter-module.md` — the step-by-step build of
  the foundation + first module.
- This file (`ARCHITECTURE.md`) — *how it actually works now.*
</content>
</invoke>
