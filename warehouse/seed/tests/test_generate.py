import csv
import datetime as dt
import hashlib
import re

import pytest

from seed.columns import BY_NAME, TABLES
from seed.generate import DATE_POINTS, REFERENCES, RESERVED_START, extra_count, generate, rows_for
from bteq.load import CONTROL_ROOT, parse_control
from bteq.parser import commands, split
from bteq.setup import DDL_ROOT


def digest_tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*.psv')}


def test_determinism_and_layout(tmp_path):
    a, b, c = (tmp_path / n for n in ('a', 'b', 'c'))
    counts = generate(2000, 1110, a)
    generate(2000, 1110, b)
    generate(2000, 1111, c)
    assert digest_tree(a) == digest_tree(b)
    assert digest_tree(a) != digest_tree(c)
    assert len(list(a.rglob('*.psv'))) == 40
    for table in TABLES:
        path = a / table.area / table.name / '20261109.psv'
        with path.open(newline='') as handle:
            rows = list(csv.reader(handle, delimiter='|'))
        assert len(rows) == counts[table.name] == table.count(2000) + extra_count(table.name)
        assert all(len(row) == len(table.columns) for row in rows)
        assert all('|' not in value and '\n' not in value and '\r' not in value for row in rows for value in row)


def test_references_and_reserved_rows():
    date = dt.date(2026, 11, 9)
    tables = {t.name: list(rows_for(t, 2000, 1110, date)) for t in TABLES}
    keys = {t.name: {row[t.names[0]] for row in tables[t.name]} for t in TABLES}
    for table in TABLES:
        for column in table.names[1:]:
            if column in REFERENCES:
                assert {row[column] for row in tables[table.name]} <= keys[REFERENCES[column]]
    plans = {row['PLAN_CODE'].strip().upper() for row in tables['PLAN_CATALOG']}
    assert all(row['PLAN_CODE'].strip().upper() in plans for row in tables['SUBSCRIPTION'])
    users = [r for r in tables['APP_USER'] if r['USER_ID'] >= RESERVED_START]
    assert len(users) == 100 and all(60 < len(r['DISPLAY_NAME']) <= 200 for r in users)
    subscriptions = [r for r in tables['SUBSCRIPTION'] if r['SUBSCRIPTION_ID'] >= RESERVED_START]
    assert len(subscriptions) == 100
    assert {r['PLAN_CODE'] for r in subscriptions} == {'pro', 'Pro ', 'TEAM  ', 'team'}
    invoices = [r for r in tables['INVOICE_HDR'] if r['INVOICE_ID'] >= RESERVED_START]
    assert {r['INVOICE_DT'] for r in invoices} == set(DATE_POINTS)
    assert {r['CURRENCY_CD'] for r in invoices} == {'usd', 'Usd', 'USD'}
    for index in range(50):
        versions = [r for r in tables['DOC_VERSION'] if r['DOCUMENT_ID'] == RESERVED_START + index]
        assert len(versions) == 2 and versions[0]['VERSION_TS'] == versions[1]['VERSION_TS']
        assert versions[0]['FILE_SIZE'] != versions[1]['FILE_SIZE']
    storage = [r for r in tables['STORAGE_USAGE_DAILY'] if r['STORAGE_USAGE_ID'] >= RESERVED_START]
    assert len(storage) == 100 and all(storage[i] == storage[i+1] for i in range(0, 100, 2))
    for name in ('APP_USER', 'SUBSCRIPTION', 'INVOICE_HDR', 'DOCUMENT', 'DOC_VERSION', 'STORAGE_USAGE_DAILY'):
        t = BY_NAME[name]
        small = {r[t.names[0]] for r in rows_for(t, 1, 1110, date) if r[t.names[0]] >= RESERVED_START}
        assert small == {r[t.names[0]] for r in tables[name] if r[t.names[0]] >= RESERVED_START}


def test_column_order_ddl_and_controls():
    found = {}
    for path in DDL_ROOT.glob('*/00_*.sql'):
        for statement in commands(path.read_text()):
            m = re.search(r'CREATE (SET|MULTISET) TABLE (SFX_\w+)\.(\w+), (?:NO )?FALLBACK \((.*)\) (?:NO |UNIQUE )?PRIMARY INDEX', statement, re.I | re.S)
            if m:
                found[m[3]] = tuple(col.strip().split()[0] for col in split(m[4], ','))
    assert len(found) == 80
    for table in TABLES:
        assert found[table.name] == found['STG_' + table.name] == table.names
        suffix, folder = ('.fl', 'fastload') if table.area in ('billing', 'users') else ('.tpt', 'tpt')
        control = parse_control(CONTROL_ROOT / folder / (table.area + '_' + table.name.lower() + suffix),
                                {'LANDING_DIR': '/data', 'BUSINESS_DATE': '20261109'})
        assert control.columns == tuple(c.lower() for c in table.names)
        assert control.path.as_posix() == f'/data/{table.area}/{table.name}/20261109.psv'


@pytest.mark.parametrize('rows,date', [(0,'20261109'),(-1,'20261109'),(1,'20260230'),(1,'2026119')])
def test_invalid_arguments(tmp_path, rows, date):
    with pytest.raises(ValueError):
        generate(rows, 1110, tmp_path, date)
    assert not list(tmp_path.iterdir())


def test_business_date(tmp_path):
    generate(1, 1110, tmp_path, '20240229')
    assert len(list(tmp_path.rglob('20240229.psv'))) == 40
