from collections import Counter
import os
from pathlib import Path
import sqlite3

import pytest

from parity.connection import COMMENT

SOURCE = (Path(__file__).resolve().parents[1] / 'billing/supplemental.sql').read_text()
FEED = 'SFX_D1110_AFTER.BILLING_PROBES.FEED'
VIEW = 'SFX_D1110_AFTER.BILLING_PROBES.SET_DUPLICATE_QUARANTINE'
DEFINITION = SOURCE.split('CREATE OR REPLACE VIEW ' + VIEW, 1)[1].split(';', 1)[0]
QUERY = 'SELECT ' + DEFINITION.split('AS SELECT ', 1)[1]


@pytest.mark.parametrize('rows', [[], [(1, 'x')], [(1, 'x')] * 2,
    [(1, 'x')] * 3 + [(1, 'y')] * 2 + [(2, 'x')],
    [(None, None)] * 2 + [(1, None)] * 3,
    [(1, 'x'), (1, 'X'), (1, 'x '), (1, 'x')]])
def test_exact_duplicate_payloads_and_extra_copy_counts(rows):
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE feed (id INTEGER, value TEXT)')
        db.executemany('INSERT INTO feed VALUES (?,?)', rows)
        actual = db.execute(QUERY.replace(FEED, 'feed')).fetchall()
        expected = [(*row, count, 1, count - 1)
                    for row, count in Counter(rows).items() if count > 1]
        assert Counter(actual) == Counter(expected)
        assert sum(row[-1] for row in actual) == len(rows) - len(set(rows))


def test_quarantine_does_not_change_set_or_multiset_conversion():
    assert f"COMMENT = '{COMMENT}'" in DEFINITION
    assert f'AS SELECT DISTINCT ID, VALUE FROM {FEED};' in SOURCE
    multiset = SOURCE.split('CREATE OR REPLACE TABLE SFX_D1110_AFTER.BILLING_PROBES.MULTISET_ROWS', 1)[1].split(';', 1)[0]
    assert f'AS SELECT * FROM {FEED}' in multiset
    assert 'BILLING.' not in DEFINITION


@pytest.mark.skipif(os.environ.get('SFX_LIVE_PARITY') != '1', reason='Live Snowflake opt-in')
def test_live_quarantine_reconciles_exact_suppressed_rows():
    from parity.connection import connect
    with connect('set_quarantine_regression') as sf, sf.cursor() as cursor:
        cursor.execute(f'SELECT ID,VALUE FROM {FEED}')
        feed = Counter(cursor.fetchall())
        cursor.execute('SELECT ID,VALUE FROM SFX_D1110_AFTER.BILLING_PROBES.SET_ROWS')
        retained = Counter(cursor.fetchall())
        assert retained == Counter({row: 1 for row in feed})
        cursor.execute(f'SELECT ID,VALUE,INPUT_COUNT,RETAINED_COUNT,SUPPRESSED_COUNT FROM {VIEW}')
        actual = cursor.fetchall()
        assert Counter(actual) == Counter([(*row, count, 1, count - 1)
                                          for row, count in feed.items() if count > 1])
        assert sum(row[-1] for row in actual) == sum(feed.values()) - sum(retained.values())
        cursor.execute('SELECT ID,VALUE FROM SFX_D1110_AFTER.BILLING_PROBES.MULTISET_ROWS')
        assert Counter(cursor.fetchall()) == feed
