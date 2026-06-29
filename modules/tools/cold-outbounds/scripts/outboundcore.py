"""Outbound/outreach core logic — pure functions (no I/O, no gspread, no IMAP)."""
import re
from datetime import date


def select_nudges(rows, today, cold_days=7):
    """Outreach rows due for a follow-up nudge.

    A row is due when: `status` is not dropped/snoozed, it has no reply, it has a
    parseable `sent_date`, and that date is at least `cold_days` old. Rows without
    a `sent_date` are skipped — there's nothing to time a nudge against.
    """
    due = []
    for r in rows:
        if str(r.get("status", "")).strip().lower() in ("dropped", "snoozed"):
            continue
        if str(r.get("replied", "")).strip().lower().startswith("replied"):
            continue
        raw = str(r.get("sent_date", "")).strip()
        if not raw:
            continue
        try:
            sent = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        if (today - sent).days >= cold_days:
            due.append(r)
    return due


def is_bulk(msg):
    """True if a message looks automated/bulk — skip it as a CRM candidate.

    `msg` is a normalized message dict with `from_email` and a `headers` dict.
    """
    h = {k.lower(): str(v) for k, v in (msg.get("headers") or {}).items()}
    if "list-unsubscribe" in h or "list-id" in h:
        return True
    if h.get("precedence", "").strip().lower() in ("bulk", "list", "junk", "auto_reply"):
        return True
    if h.get("auto-submitted", "no").strip().lower() not in ("", "no"):
        return True
    local = str(msg.get("from_email", "")).split("@", 1)[0].lower()
    if re.search(r"no-?reply|do-?not-?reply|donotreply|mailer-daemon|notifications?|postmaster|bounce", local):
        return True
    return False


def derive_status(thread, today, cold_days=7):
    """Reply status of an outreach thread from its last outbound/inbound dates.

    `thread`: {"last_outbound": date|None, "last_inbound": date|None}.
    Returns {"status": "replied"|"cold"|"awaiting", "days_since": int|None}.
    """
    lo = thread.get("last_outbound")
    li = thread.get("last_inbound")
    if li and (lo is None or li >= lo):
        return {"status": "replied", "days_since": (today - lo).days if lo else None}
    if lo is not None:
        days = (today - lo).days
        return {"status": "cold" if days >= cold_days else "awaiting", "days_since": days}
    return {"status": "awaiting", "days_since": None}


def _email_like(s):
    s = (s or "").strip().lower()
    return "@" in s and "." in s.rsplit("@", 1)[-1]


def counterpart(msg, mine):
    """The external party's email for a normalized message; '' if none.

    `mine` is a set of my own lowercased addresses (to exclude). For outbound
    messages the counterpart is the first non-self recipient; for inbound, the sender.
    """
    if msg.get("direction") == "outbound":
        cands = msg.get("to_emails") or []
    else:
        cands = [msg.get("from_email")]
    for a in cands:
        a = (a or "").strip().lower()
        if a and a not in mine and _email_like(a):
            return a
    return ""


def build_threads(msgs, mine, max_subject=140):
    """Aggregate normalized messages by external counterpart email.

    Returns {email: {last_outbound: date|None, last_inbound: date|None,
                     subject: str, account: str, n_out: int, n_in: int}}.
    `subject` tracks the latest outbound subject. `mine` is a set of my addresses.
    """
    threads = {}
    for m in msgs:
        cp = counterpart(m, mine)
        if not cp:
            continue
        d = None
        raw = m.get("date_utc")
        if raw:
            try:
                d = date.fromisoformat(str(raw)[:10])
            except ValueError:
                d = None
        t = threads.setdefault(cp, {"last_outbound": None, "last_inbound": None,
                                    "subject": "", "account": m.get("account", ""),
                                    "n_out": 0, "n_in": 0})
        if m.get("direction") == "outbound":
            t["n_out"] += 1
            if d and (t["last_outbound"] is None or d > t["last_outbound"]):
                t["last_outbound"] = d
                t["subject"] = (m.get("subject") or "")[:max_subject]
        else:
            t["n_in"] += 1
            if d and (t["last_inbound"] is None or d > t["last_inbound"]):
                t["last_inbound"] = d
    return threads


def initiated(subject):
    """True if an outbound subject looks like a thread I started, not a reply/forward."""
    s = (subject or "").strip().lower()
    return bool(s) and not s.startswith(("re:", "fwd:", "fw:"))
