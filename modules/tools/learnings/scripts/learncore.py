"""Pure helpers for the learnings loop — no I/O, unit-tested.

A "learning" is a dict: {id, ts, skill, insight, why, importance, status}.
importance ∈ {low, med, high}; status ∈ {new, promoted, dismissed}.
"""
import re

IMPORTANCE = ("low", "med", "high")
STATUS = ("new", "promoted", "dismissed")
_RANK = {name: i for i, name in enumerate(IMPORTANCE)}
_LABEL = {"high": "HIGH", "med": "MED", "low": "LOW"}


def normalize(text):
    """Lowercase, collapse internal whitespace, strip — for dedup keys."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def importance_rank(importance):
    """Numeric rank for sorting/thresholding; unknown -> -1 (below low)."""
    return _RANK.get(str(importance or "").strip().lower(), -1)


def find_dup(records, skill, insight):
    """First record matching (skill, insight) case/space-insensitively, ANY status.

    Matching against all statuses means a dismissed or already-promoted learning
    won't resurface when the agent re-derives it across sessions.
    """
    k_skill, k_insight = normalize(skill), normalize(insight)
    for r in records:
        if normalize(r.get("skill")) == k_skill and normalize(r.get("insight")) == k_insight:
            return r
    return None


def filter_pending(records, floor="med"):
    """`new` records at or above the importance floor, high->low then oldest-first."""
    fr = importance_rank(floor)
    out = [r for r in records
           if r.get("status") == "new" and importance_rank(r.get("importance")) >= fr]
    out.sort(key=lambda r: (-importance_rank(r.get("importance")), str(r.get("ts", ""))))
    return out


def apply_review(records, learning_id, status):
    """Return (new_records, found). Sets status on the record whose id matches."""
    found = False
    out = []
    for r in records:
        if r.get("id") == learning_id:
            r = {**r, "status": status}
            found = True
        out.append(r)
    return out, found


def format_digest(pending):
    """Grouped Telegram digest text for pending learnings. Empty string if none."""
    if not pending:
        return ""
    n = len(pending)
    lines = [f"🧠 {n} learning{'' if n == 1 else 's'} to review", ""]
    for level in ("high", "med", "low"):
        group = [r for r in pending
                 if importance_rank(r.get("importance")) == importance_rank(level)]
        if not group:
            continue
        lines.append(_LABEL[level])
        for r in group:
            lines.append(f"• [{r.get('id', '?')}] {r.get('skill', '?')} — {r.get('insight', '')}")
            why = str(r.get("why", "")).strip()
            if why:
                lines.append(f"    why: {why}")
        lines.append("")
    lines.append('Promote the good ones into the skill (git), then tell me '
                 'e.g. "promoted L-a1b2c3" / "dismiss L-a1b2c3".')
    return "\n".join(lines)
