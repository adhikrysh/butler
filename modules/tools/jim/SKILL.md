---
name: jim
description: the user's personal coach + structured training log (his `butler` Google Sheet: Jim Sessions / Programme / Goals tabs). Use WHENEVER he mentions training — "going to the gym / for a run", "about to train", reports a workout or sets/reps/times (even a bare line like "leg extension 80x8, 100x8"), sets or changes a fitness goal or programme, or asks about training, progress, PRs, or what to do today. Plain statements MUST trigger it, not only questions.
---

# jim — personal coach (structured)

Training lives in SQLite (`butler.db`, source of truth) fronted by 3 Sheet tabs
(Jim Sessions / Programme / Goals). You operate it via `jim.py`. Data is per-set
granular, so you can answer real progress questions.

## ⚠️ The one rule
**Log BEFORE you reply. Never give feedback on a workout without logging it first.**
The DB is the only durable store; if no command ran, it did NOT happen.

## Load context: `uv run /home/drc/butler/modules/tools/jim/scripts/jim.py current`
Returns active programme (+ today's day), goals with target-vs-current, recent
sessions, PRs, Garmin readiness. Reason over THIS.

## Logging a workout — YOU structure it, then log
Parse his numbers into structured sets and call `log`. Disambiguate his notation:
`80x8` = 80 kg × 8 reps; `8x110` = 8 reps × 110 kg; `8x95x2` = 8 reps × 95 kg, two sets.
```
uv run /home/drc/butler/modules/tools/jim/scripts/jim.py log --json '{"type":"strength","title":"Leg day","duration_min":60,"rpe":8,"feel":"first leg day","exercises":[{"exercise":"leg extension","sets":[{"weight":80,"reps":8},{"weight":100,"reps":8},{"weight":120,"reps":8},{"weight":140,"reps":8}]},{"exercise":"ham curls","sets":[{"weight":110,"reps":8},{"weight":95,"reps":8},{"weight":95,"reps":8}]}]}'
```
Cardio: `{"type":"run","title":"Easy 10k"}` — jim auto-fills distance/HR/pace from the FR955. Fill `duration_min`/`rpe`/`feel` from what he said.

## Setting goals → also generate + store a programme
When he states goals/constraints (e.g. "75 kg, gym 5×/week, 1 hr"), design a weekly
split and STORE it, and record the goals:
```
uv run .../jim.py plan --json '{"name":"Block A","freq_per_week":5,"days":[{"day":"A","focus":"legs","exercises":[{"exercise":"squat","sets":4,"reps":5,"load":"RPE8"},{"exercise":"leg extension","sets":4,"reps":8}]}]}'
uv run .../jim.py goal --json '{"metric":"bodyweight","target":"75","current":"68","unit":"kg","deadline":"2026-12-01"}'
```
Never leave him without a stored programme.
Update a goal's current/status later: `jim.py goal-update --match '{"metric":"bodyweight"}' --json '{"current":"70","status":"active"}'`.

## Progress: `jim.py progress [--exercise "leg extension"]`
Real numbers — per-exercise progression, weekly volume/frequency vs the programme
(adherence), PRs. Report grounded, cite web facts via tinyfish when relevant.

## Other: `jim.py prs`, `dump`, `resync` (rebuild the Sheet tabs from the DB).
Reason only over command output; the sheet is a view.
