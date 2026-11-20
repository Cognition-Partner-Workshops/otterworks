import csv
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_daily
from backfill_diff import report


@pytest.mark.parametrize("kind", ["good", "empty", "drift", "error", "unknown", "date", "money", "active"])
def test_local_load(tmp_path, monkeypatch, kind):
    landing = tmp_path / "landing"
    landing.mkdir()
    source = load_daily.ROOT / "landing/2026-11-09.csv"
    with source.open(newline="") as stream:
        rows = list(csv.reader(stream))
    monkeypatch.setattr(load_daily, "ROOT", tmp_path)
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("SFX_LOG_PATH", str(log))
    path = landing / source.name
    db = tmp_path / "target.duckdb"

    def write(records):
        with path.open("w", newline="") as stream:
            csv.writer(stream).writerows(records)

    def run():
        load_daily.load(load_daily.GOOD_DATE, no_build=True, target="duckdb", db_path=db)

    write(rows)
    run()
    if kind == "empty":
        rows = rows[:1]
    elif kind == "drift":
        rows[0].insert(0, "DISCOUNT_CODE")
        for row in rows[1:]:
            row[1] = "CUST-0001"
            row.insert(0, "LOYALTY10")
    elif kind == "error":
        rows[1][0] = "999999999999999999999999"
    elif kind in ("unknown", "date", "money", "active"):
        index, value = {"unknown": (1, "OTHER-0001"), "date": (4, "11/10/2026"),
                        "money": (7, "not-money"), "active": (10, "MAYBE")}[kind]
        rows[1][index] = value
    write(rows)
    if kind == "error":
        with pytest.raises(duckdb.ConversionException):
            run()
    elif kind in ("unknown", "date", "money", "active"):
        with pytest.raises(load_daily.SafeLoadError, match="count=1, sample="):
            run()
    else:
        run()
        run()
    with duckdb.connect(str(db)) as connection:
        count, nulls = connection.execute("SELECT count(*),count(*) FILTER (WHERE CUSTOMER_ID IS NULL) FROM RAW_BILLING.USAGE_DAILY").fetchone()
    assert count == (0 if kind == "empty" else 48)
    assert nulls == 0
    events = [json.loads(line)["event"] for line in log.read_text().splitlines()]
    assert events[-1] == ("load_failure" if kind in ("error", "unknown", "date", "money", "active") else "load_success")


@pytest.mark.parametrize('column,value', [('USAGE_DAILY_ID', 'not-an-id'),
    ('CUSTOMER_ID', 'CUST-0001-extra'), ('QUANTITY', 'eighty'),
    ('UNIT_PRICE', 'unknown'), ('CREATED_AT', 'not-a-timestamp')])
def test_cast_diagnostics(column, value, tmp_path, monkeypatch):
    landing = tmp_path / 'landing'
    landing.mkdir()
    with (load_daily.ROOT / 'landing/2026-11-09.csv').open(newline='') as stream:
        rows = list(csv.reader(stream))
    rows[1][rows[0].index(column)] = value
    with (landing / '2026-11-09.csv').open('w', newline='') as stream:
        csv.writer(stream).writerows(rows)
    monkeypatch.setattr(load_daily, 'ROOT', tmp_path)
    monkeypatch.setenv('SFX_LOG_PATH', str(tmp_path / 'events.jsonl'))
    db = tmp_path / 'test.duckdb'
    with pytest.raises(load_daily.SafeLoadError, match=f'{column}: count=1'):
        load_daily.load(load_daily.GOOD_DATE, target='duckdb', db_path=db, no_build=True)
    with duckdb.connect(str(db)) as connection:
        assert connection.execute('SELECT COUNT(*) FROM RAW_BILLING.USAGE_DAILY').fetchone()[0] == 0


def test_backfill_diff_preserves_multiplicity(tmp_path):
    before, after = tmp_path / 'before.duckdb', tmp_path / 'after.duckdb'
    for path, values in [(before, [(1, 10), (2, 20)]), (after, [(1, 10), (1, 10)])]:
        with duckdb.connect(str(path)) as connection:
            connection.execute('CREATE SCHEMA RAW_BILLING')
            connection.execute('CREATE TABLE RAW_BILLING.USAGE_DAILY (USAGE_DAILY_ID BIGINT, AMOUNT INTEGER, _SRC_FILE VARCHAR, _LOADED_AT TIMESTAMP)')
            connection.executemany("INSERT INTO RAW_BILLING.USAGE_DAILY VALUES (?,?,'day',CURRENT_TIMESTAMP)", values)
    result = report(before, after)
    assert '| day | before | 2 | 2 | 0 | 30 |' in result
    assert '| day | after | 2 | 1 | 1 | 20 |' in result
    assert '**2 changed keys**' in result
    assert '**False**' in result
    assert '**0 changed keys**' in report(before, before)
    with pytest.raises(duckdb.IOException):
        report(before, tmp_path / 'missing.duckdb')
