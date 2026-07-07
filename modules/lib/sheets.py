"""Shared Sheets layer for the `butler` spreadsheet — generic gspread wrapper.

Imported by the sheet-backed modules (ppl-index, cold-outbounds, superforecasting):
one Google Sheet, many tabs. Pure helpers (record_to_row, match_index) import
without gspread; the Sheet class needs gspread + the service-account auth. Reuses
CRM_SHEET_ID / CRM_SA_KEY from the profile .env. Header row = schema (read live,
never positional), with retry/backoff on transient 429/5xx.
"""
import os
import time
import re as _re


def record_to_row(headers: list[str], record: dict) -> list[str]:
    """Map a record dict to cell values ordered by headers; missing keys -> ''."""
    return [str(record.get(h, "")) for h in headers]


def match_index(rows: list[dict], match: dict) -> int | None:
    """First index where every key in match is equal (string-compared)."""
    for i, row in enumerate(rows):
        if all(str(row.get(k, "")) == str(v) for k, v in match.items()):
            return i
    return None


def a1_row_from_range(updated_range: str) -> int | None:
    """Parse the first row number out of an A1 range like 'Jim!A42:J42' -> 42."""
    m = _re.search(r"[A-Z]+(\d+)", updated_range or "")
    return int(m.group(1)) if m else None


def _col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _retry(fn, tries: int = 6, base: float = 0.8):
    import gspread
    for n in range(tries):
        try:
            return fn()
        except gspread.exceptions.APIError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (429, 500, 503) and n < tries - 1:
                time.sleep(base * (2 ** n))
                continue
            raise


class Sheet:
    """Thin gspread wrapper. Header row is the schema — never hardcodes positions."""

    def __init__(self):
        import gspread
        sa = os.environ.get("CRM_SA_KEY") or os.path.expanduser("~/.hermes/profiles/butler/crm_google_sa.json")
        self._gc = gspread.service_account(filename=sa)
        self._ss = self._gc.open_by_key(os.environ["CRM_SHEET_ID"])

    def _ws(self, tab: str):
        return _retry(lambda: self._ss.worksheet(tab))

    def records(self, tab: str) -> list[dict]:
        ws = self._ws(tab)
        return _retry(lambda: ws.get_all_records())

    def tabs(self) -> list[str]:
        """All worksheet (tab) titles in the spreadsheet."""
        return _retry(lambda: [w.title for w in self._ss.worksheets()])

    def values(self, tab: str) -> list[list[str]]:
        """Raw cell values (header + data rows) for a tab — for verbatim export."""
        ws = self._ws(tab)
        return _retry(lambda: ws.get_all_values())

    def append(self, tab: str, record: dict) -> dict:
        ws = self._ws(tab)
        headers = _retry(lambda: ws.row_values(1))
        _retry(lambda: ws.append_row(record_to_row(headers, record), value_input_option="USER_ENTERED"))
        return record

    def ensure_tab(self, tab: str, headers: list[str]):
        """Create the tab with a header row if it doesn't exist. Idempotent."""
        if tab not in self.tabs():
            ws = _retry(lambda: self._ss.add_worksheet(
                title=tab, rows=200, cols=max(len(headers), 12)))
            _retry(lambda: ws.update([headers]))
        return tab

    def append_colored(self, tab: str, record: dict, background: dict | None = None) -> dict:
        """Append a row; optionally set its background color (e.g. meta rows).
        background is a gspread color dict, e.g. {'red':1,'green':0.949,'blue':0.8}."""
        ws = self._ws(tab)
        headers = _retry(lambda: ws.row_values(1))
        resp = _retry(lambda: ws.append_row(
            record_to_row(headers, record), value_input_option="USER_ENTERED"))
        if background:
            rng = ((resp or {}).get("updates") or {}).get("updatedRange", "")
            row = a1_row_from_range(rng)
            if row:
                last_col = _col_letter(len(headers))
                _retry(lambda: ws.format(f"A{row}:{last_col}{row}",
                                         {"backgroundColor": background}))
        return record

    def update(self, tab: str, match: dict, changes: dict) -> dict | None:
        import gspread
        ws = self._ws(tab)
        headers = _retry(lambda: ws.row_values(1))
        rows = _retry(lambda: ws.get_all_records())
        i = match_index(rows, match)
        if i is None:
            return None
        rownum = i + 2  # +1 header, +1 for 1-based
        cells = [gspread.Cell(rownum, col, str(changes[h]))
                 for col, h in enumerate(headers, start=1) if h in changes]
        if cells:
            _retry(lambda: ws.update_cells(cells, value_input_option="USER_ENTERED"))
        return {**rows[i], **changes}
