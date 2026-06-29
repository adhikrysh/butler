"""Shared Sheets layer for the `butler` spreadsheet — generic gspread wrapper.

Imported by the sheet-backed modules (ppl-index, cold-outbounds, superforecasting):
one Google Sheet, many tabs. Pure helpers (record_to_row, match_index) import
without gspread; the Sheet class needs gspread + the service-account auth. Reuses
CRM_SHEET_ID / CRM_SA_KEY from the profile .env. Header row = schema (read live,
never positional), with retry/backoff on transient 429/5xx.
"""
import os
import time


def record_to_row(headers: list[str], record: dict) -> list[str]:
    """Map a record dict to cell values ordered by headers; missing keys -> ''."""
    return [str(record.get(h, "")) for h in headers]


def match_index(rows: list[dict], match: dict) -> int | None:
    """First index where every key in match is equal (string-compared)."""
    for i, row in enumerate(rows):
        if all(str(row.get(k, "")) == str(v) for k, v in match.items()):
            return i
    return None


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
