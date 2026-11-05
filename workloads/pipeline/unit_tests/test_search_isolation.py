import re
import sqlite3
from pathlib import Path

import pytest
from jinja2 import Environment


@pytest.mark.parametrize("hits,expected", [
    ([], []),
    ([("own",)], [("own", "Own title")]),
    ([("other",)], []),
    ([("own",), ("other",), ("deleted",), ("missing",)], [("own", "Own title")]),
])
def test_document_hits_cannot_expose_another_accounts_title(hits, expected):
    path = Path(__file__).resolve().parents[1] / "macros/search_items.sql"
    macro = Environment().from_string(path.read_text()).module.search_items
    sql = macro("events", "documents", "periods")
    docs = re.search(r"\), docs as \((.*?)\), combined as", sql, re.S).group(1)
    docs = re.sub(r"::(?:varchar\(\d+\)|number\(\d+,\d+\))", "", docs)
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE documents(id TEXT,owner_id TEXT,title TEXT,is_deleted BOOLEAN)")
        conn.executemany("INSERT INTO documents VALUES (?,?,?,?)", [
            ("own", "account-a", "Own title", False),
            ("other", "account-b", "Private B title", False),
            ("deleted", "account-a", "Deleted title", True),
        ])
        conn.execute("CREATE TABLE appearances(window_end_date TEXT,account_id TEXT,event_id TEXT,searched_at TEXT,document_id TEXT)")
        conn.executemany("INSERT INTO appearances VALUES ('2026-11-01','account-a','event-1','2026-10-31',?)", hits)
        rows = conn.execute(docs).fetchall()
    assert [(r[4], r[5]) for r in rows] == expected
