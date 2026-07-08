# jim — autoregulation rules (principles × his data)

Concrete `condition → action` rules that fuse the canon with what `jim.py current`
and his logged sets actually say. These are defaults, not laws — state your reasoning
and the number you're reading. Recovery data lives in `current.garmin.recovery`,
fitness in `current.garmin.fitness`, sets in the DB (`progress`/`prs`/`dump`).

## Recovery gating (all phases) — before prescribing today
Read `garmin.recovery`: `readiness_score`/`readiness_level`, `recovery_time_hours`,
`body_battery_recent`, `sleep_score`, `hrv_status`, `resting_hr`.

- **Green** (readiness ≥ ~65 / HRV `BALANCED` / slept well / low recovery-time) →
  **push**: progress load or add the planned hard set.
- **Amber** (readiness ~45–65, or one bad marker — poor sleep OR suppressed HRV) →
  **hold**: hit the plan but don't chase PRs; cap top sets at ~2 RIR.
- **Red** (readiness < ~45, HRV `UNBALANCED`/low, high `recovery_time_hours`, poor
  sleep stacking) → **deload today**: cut volume ~30–50% or swap to technique/mobility.
  Say why ("your HRV's suppressed and you slept 5h — today we bank a quality easy
  session, not a grind"). This *is* the Mundanity ethos: protect the streak.

## Progression — novice (double progression)
From his logged sets for the lift:
- Hit **all** top sets at target reps with **RIR ≤ 1–2** → **+load** (or +reps if below
  the rep-range top) next session.
- **Missed the top set twice in a row** → repeat the weight, or micro-deload ~10% and
  build back. Don't grind a stalling linear lift into the ground.

## Volume — intermediate (RP landmarks)
Compute weekly hard sets per muscle from `jim_sets` (use the exercise→muscle map).
- **< MEV** and recovering fine → **add a set** to that muscle next week.
- **At/near MRV** with recovery markers dropping (readiness/HRV/RHR trending bad,
  sleep down) → **deload** the muscle/block.
- Landmarks are individual — start from population defaults (~10 MEV / ~20 MRV for most
  muscles) and adjust from HIS recovery response, not a table.

## Running — 80/20 policing
From a logged run + `enrich_session` HR:
- **Easy run with avg HR above Z2** → flag it: *"that easy run averaged Z3 — the 80/20
  rule wants your easy days genuinely easy so they don't tax your legs for squats."*
- Keep hard running sessions purposeful and few; don't let daily medium-hard cardio
  erode lifting recovery (watch `training_status` = `AEROBIC_*_SHORTAGE`/overreaching).

## Deload trigger (programmed)
- **Performance stall ≥ 2–3 sessions** on a lift **+ elevated fatigue markers**
  (readiness down, HRV suppressed, RHR up vs baseline) → schedule a **deload week**
  (~50% volume, submaximal loads), then resume. Fatigue masking fitness ≠ weakness.

## Goal tracking — read the real series
- **Bodyweight (68→75):** read `garmin.body.latest_kg` / weight trend (he logs weight
  → it's written to Garmin). Judge the *trend slope* vs the deadline, not one weigh-in;
  ~0.25–0.5 kg/week is a sane lean-gain rate — faster is mostly fat.
- **Running goals:** read `garmin.fitness.race_predictions` + VO₂max trend.
- **Lift goals:** read computed e1RM PRs (`jim.py prs`).

## The through-line
When in doubt, coach the leading indicator: did he show up, progress a little, sleep,
eat his protein? Reward that. Excellence is those mundane things, compounded.
