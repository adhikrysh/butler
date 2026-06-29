# Thread + LinkedIn enrichment

Use this when the user gives a LinkedIn URL plus a freeform message/thread summary.

## What to persist
- `linkedin`: always add immediately if provided.
- `title` / `company`: take from LinkedIn when visible; otherwise use the user's description.
- `met_where`: convert the prompt into the concrete source of the relationship:
  - event / conference / meetup / call / intro / message thread
- `notes`: preserve the useful content:
  - what they do
  - why they matter
  - any advice / warning / follow-up signal
  - short reply-thread summary if the user included one

## Good habits
- Prefer grounded specifics over generic labels.
- Keep relationship facts in the right fields; keep interpretation in `notes`.
- Do not leave title/company/how-met blank just because the user gave them informally in prose.
