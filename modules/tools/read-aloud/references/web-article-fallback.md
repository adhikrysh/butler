# Web article reading fallback

Use this when the source is a long URL and the primary read-aloud script is not the best path.

## Reliable extraction path
1. Fetch the page text first with `mcp_tinyfish_fetch_content` in `markdown` format.
2. Treat the returned text as the source of truth for chunking and narration.
3. Keep headings and paragraph breaks when possible; they improve spoken pacing.

## Chunking guidance
- Target roughly 2,500–3,000 characters per chunk.
- Split on paragraph boundaries first.
- If a paragraph is too long, split on sentence boundaries.
- Keep chunks short enough that synthesis is stable and the playback order is obvious.

## When the canonical script is unavailable
- If the standard read-aloud script cannot be used, synthesize from the extracted text instead of stopping.
- Deliver the audio as sequential chunks or a single merged file, whichever is more practical for the environment.

## Quality checks
- Confirm the article title and ending are included.
- Verify that the final chunk covers the last paragraph or subscription/paywall notice if present.
- Avoid adding commentary into the narration unless the user asked for it.
