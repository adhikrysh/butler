# Bulk contact intake + enrichment

Use this pattern when the user dumps several people at once or gives only partial identity details.

## Intake
- Add each person immediately to `ppl-index` (via `contacts.py add`) with whatever is known.
- Leave unknown fields blank; do not block on completeness.
- Keep `notes` factual and compact: where you met them, what they do, and the memorable takeaway.

## Enrichment (via the tinyfish MCP)
- Use tinyfish `search` (free) to find each person's LinkedIn / X / GitHub / site; read with `fetch_content`; escalate to `run_web_automation` for JS/auth-walled pages (LinkedIn, X).
- For a batch, `batch_create` runs many enrichments at once.
- Prefer public, confirmable URLs over guessed handles. If multiple profiles exist, pick the one whose headline/company/location best matches the notes.

## Tooling
- For batch adds, build the JSON payload programmatically rather than hand-nesting shell quotes.
- When a command gets quote-heavy, use Python to construct the payload and pass it through `shell_quote(...)` (see `safe-json-shelling.md`).
- Verify the row by dumping or finding the contact if the write matters.

## Reply style
- Confirm what was added and where each fact came from.
- Offer at most one short follow-up question for missing high-value fields (email, title, company, met_where).
