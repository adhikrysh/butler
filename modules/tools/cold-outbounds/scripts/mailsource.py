"""Read-only IMAP mail source for the outreach email sync. Multi-account (Gmail, iCloud).

Fetches recent Sent (outbound) + INBOX (inbound) message HEADERS with BODY.PEEK —
never marks anything read — and normalizes to a common shape. No sheet I/O.
Creds come from the profile .env (GMAIL_ADDR/_APP_PW, ICLOUD_ADDR/_APP_PW); an
account with missing creds is skipped.
"""
import os
import re
import email
import imaplib
from email.utils import parsedate_to_datetime, getaddresses
from email.header import decode_header, make_header
from datetime import datetime, timezone, timedelta

ACCOUNTS = {
    "gmail":  {"host": "imap.gmail.com",   "addr": "GMAIL_ADDR",  "pw": "GMAIL_APP_PW",  "sent_fallback": "[Gmail]/Sent Mail"},
    "icloud": {"host": "imap.mail.me.com", "addr": "ICLOUD_ADDR", "pw": "ICLOUD_APP_PW", "sent_fallback": "Sent Messages"},
}

_FIELDS = ("(BODY.PEEK[HEADER.FIELDS (FROM TO CC DATE SUBJECT MESSAGE-ID "
           "IN-REPLY-TO REFERENCES LIST-UNSUBSCRIBE LIST-ID PRECEDENCE AUTO-SUBMITTED)])")


def _one(s):
    a = getaddresses([s or ""])
    return (a[0][1] if a else "").lower()


def _many(s):
    return [addr.lower() for _, addr in getaddresses([s or ""]) if addr]


def _decode(s):
    """Decode an RFC 2047-encoded header (e.g. =?utf-8?Q?...?=) to plain text."""
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s


def _normalize(raw, account, direction):
    m = email.message_from_bytes(raw)
    try:
        dt = parsedate_to_datetime(m.get("Date"))
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        date_utc = dt.astimezone(timezone.utc).isoformat() if dt else None
    except Exception:
        date_utc = None
    return {
        "account": account,
        "direction": direction,
        "from_email": _one(m.get("From")),
        "to_emails": _many(m.get("To")) + _many(m.get("Cc")),
        "date_utc": date_utc,
        "subject": _decode(m.get("Subject")).strip(),
        "message_id": (m.get("Message-ID") or "").strip(),
        "in_reply_to": (m.get("In-Reply-To") or "").strip(),
        "references": (m.get("References") or "").strip(),
        "headers": {k: v for k, v in m.items()},
    }


def _sent_folder(M, fallback):
    """Find the \\Sent special-use folder; fall back to the known name."""
    try:
        typ, folders = M.list()
        if typ == "OK":
            for f in folders:
                line = f.decode("utf-8", "ignore") if isinstance(f, bytes) else str(f)
                if r"\Sent" in line:
                    mt = re.search(r'"([^"]*)"\s*$', line)
                    if mt:
                        return mt.group(1)
    except Exception:
        pass
    return fallback


def fetch_recent(account, since_days=90, limit=500):
    cfg = ACCOUNTS[account]
    user, pw = os.environ.get(cfg["addr"]), os.environ.get(cfg["pw"])
    if not user or not pw:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
    out = []
    M = imaplib.IMAP4_SSL(cfg["host"], 993)
    try:
        M.login(user, pw)
        for folder, direction in ((_sent_folder(M, cfg["sent_fallback"]), "outbound"), ("INBOX", "inbound")):
            typ, _ = M.select(f'"{folder}"', readonly=True)  # quote: folder names can contain spaces
            if typ != "OK":
                continue
            typ, data = M.search(None, "SINCE", since)
            if typ != "OK" or not data or not data[0]:
                continue
            ids = data[0].split()[-limit:]
            typ, fetched = M.fetch(",".join(i.decode() for i in ids), _FIELDS)
            if typ != "OK":
                continue
            for part in fetched:
                if isinstance(part, tuple) and len(part) > 1 and part[1]:
                    out.append(_normalize(part[1], account, direction))
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return out


def fetch_all(since_days=90, limit=500):
    msgs = []
    for acct in ACCOUNTS:
        msgs.extend(fetch_recent(acct, since_days, limit))
    return msgs
