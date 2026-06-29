from sheets import record_to_row, match_index


def test_record_to_row_orders_by_header_and_blanks_missing():
    headers = ["name", "email", "company"]
    assert record_to_row(headers, {"company": "Acme", "name": "Jane"}) == ["Jane", "", "Acme"]


def test_record_to_row_ignores_unknown_keys():
    headers = ["name", "email"]
    assert record_to_row(headers, {"name": "Jane", "phone": "x"}) == ["Jane", ""]


def test_match_index_finds_first_all_keys_match():
    rows = [{"email": "a@example.com", "name": "A"}, {"email": "b@example.com", "name": "B"}]
    assert match_index(rows, {"email": "b@example.com"}) == 1


def test_match_index_returns_none_when_absent():
    assert match_index([{"email": "a@example.com"}], {"email": "z@example.com"}) is None
