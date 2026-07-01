---
name: superforecasting
description: the user's decision journal (the `superforecasting` tab of his `butler` Google Sheet). Use WHENEVER the user states a decision, bet, prediction, or call he's making — "I'm going with X", "betting that Y", "decided to Z", "I think X will happen" — log it before replying. Also use when he replies to the daily decision check-in, reports how a past call turned out, or asks about his decisions or his calibration.
---

# Superforecasting — decision journal

A calibration instrument, not a diary. the user logs each decision with a **probability** and a **falsifiable expected outcome**; later he reviews what actually happened. Over time this measures — and trains — his judgment. You operate it with `forecast.py` over the `superforecasting` tab of the same sheet as the CRM.

## Why each field exists (the discipline)
- **confidence** — a *number* (e.g. 70%), never a word. "Likely" can't be scored; 70% can.
- **expected** — what success concretely looks like, fixed up front, so the review is unambiguous.
- **rationale** — the *why*, captured now, before hindsight quietly rewrites it.
- **review_date** — when to resurface (default 3 months).
- At review, judge the **decision, not the outcome**. A 70% bet that lost can still have been right — it was *supposed* to lose 30% of the time. Grade the reasoning given what he knew. That's `verdict` (right / wrong / mixed).

## Commands
Log a decision (run this BEFORE you reply when the user states a call):
```
uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py log --json '{"decision":"raise async instead of a priced round","rationale":"more leverage while metrics ramp","confidence":"70%","expected":"signed term sheet by Q4"}' --window "3 months"
```
Decisions due for review:
```
uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py due
```
Record how one turned out (judge the reasoning, not just the result):
```
uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py review --match '{"decision":"raise async instead of a priced round"}' --json '{"outcome":"closed in Q4 at target","verdict":"right","status":"reviewed"}'
```
Calibration report / full dump:
```
uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py calibration
uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py dump
```

## Behavior
- **Decision stated → `log` immediately, before replying.** Pull out the `decision`, the `rationale`, a `confidence` **as a %**, and the `expected` outcome / success criteria. Default the window to 3 months unless he says otherwise. The sheet is the only durable store — never claim you logged something unless the command just ran and did it.
- **Vague on probability → press once.** "Pretty confident" → "call it — 70%? 80%?" A decision with no number can't be scored, and the number is the whole point.
- **No clear success criteria → ask for one in the same breath.** "What would tell us this worked, and by when?"
- **Daily check-in reply → log it, or accept "none".** When he answers the daily prompt with a call, log it. "none" is a valid, guilt-free answer — never manufacture a decision to fill the log.
- **Reviewing → `review` with outcome + verdict.** When he reports how a call went (or answers a due review), capture the `outcome`, set `verdict` on whether the *reasoning* was sound (right / wrong / mixed), and `status` to `reviewed`.
- **Calibration on request → run `calibration` and report the gap** between his stated confidence and his actual hit rate (over- or under-confident), plainly.
- **Quote-heavy text → build the JSON payload in Python and `shell_quote` it** before calling `forecast.py`; don't hand-nest quotes in the shell.
