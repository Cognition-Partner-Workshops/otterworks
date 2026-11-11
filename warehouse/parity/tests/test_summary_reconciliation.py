"""Execute the rendered summary query and hooks offline with SQLite."""
from pathlib import Path
import sqlite3

from jinja2 import Environment
import pytest
import sqlglot


@pytest.mark.parametrize('events', [
    [(1, '2026-11-10', 2, 'DOC_EXPORT'), (2, '2026-11-09', 1, 'DOC_VIEW')],
    [(1, '2026-11-10', 2, 'DOC_EXPORT')],
    [(1, '2026-11-10', None, 'DOC_EXPORT')],
    [],
])
def test_incremental_summary_reconciles_moved_and_removed_groups(events):
    db = sqlite3.connect(':memory:')
    db.create_function('EQUAL_NULL', 2, lambda a, b: a == b)
    db.execute('create table events(EVENT_ID int, EVENT_TS text, CUSTOMER_ID int, EVENT_TYPE text)')
    db.execute('create table summary(SUMMARY_ID int primary key, SUMMARY_DT text, CUSTOMER_ID int, '
               'EVENT_COUNT int, EXPORT_COUNT int)')
    db.executemany('insert into summary values (?, ?, ?, ?, ?)',
                   [(50001, '2026-11-09', 1, 2, 1), (50002, '2026-11-08', 3, 1, 0)])
    db.executemany('insert into events values (?, ?, ?, ?)', events)
    config = {}
    def capture(**kwargs):
        config.update(kwargs)
        return ''
    context = dict(config=capture, var=lambda name, default: default,
                   ref=lambda name: 'events', this='summary', is_incremental=lambda: True)
    env = Environment()
    model = Path(__file__).resolve().parents[2] / 'dbt/models/pc/audit/pc_audit__audit_daily_summary.sql'
    sql = env.from_string(model.read_text()).render(**context)
    def execute(sql):
        return db.execute(sqlglot.transpile(sql, read='snowflake', write='sqlite')[0])
    rows = execute(sql).fetchall()
    db.executemany('insert or replace into summary values (?, ?, ?, ?, ?)', rows)
    for hook in config.get('post_hook', []):
        execute(env.from_string(hook).render(**context))
    expected = db.execute("select EVENT_TS, CUSTOMER_ID, count(EVENT_ID), "
                          "sum(EVENT_TYPE = 'DOC_EXPORT') from events group by 1, 2").fetchall()
    actual = db.execute('select SUMMARY_DT, CUSTOMER_ID, EVENT_COUNT, EXPORT_COUNT from summary').fetchall()
    assert sorted(actual, key=str) == sorted(expected, key=str)
    ids = {(dt, customer): id_ for id_, dt, customer, *_ in db.execute('select * from summary')}
    if ('2026-11-09', 1) in ids:
        assert ids['2026-11-09', 1] == 50001
    assert all(id_ == 50003 for key, id_ in ids.items() if key != ('2026-11-09', 1))
