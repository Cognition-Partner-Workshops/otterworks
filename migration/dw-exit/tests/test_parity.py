import json
import importlib.util
import os
from pathlib import Path

import pytest

from parity.ladder import Ladder, assert_parity, identifier, relation
from parity.report import table

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(os.environ.get('SFX_PARITY_MANIFEST', ROOT / 'parity/billing.json'))
ENTRIES = json.loads(MANIFEST.read_text())


@pytest.fixture(scope='session')
def live_results():
    if os.environ.get('SFX_LIVE_PARITY') != '1':
        pytest.skip('Set SFX_LIVE_PARITY=1 to query live Snowflake')
    from parity.connection import connect
    with connect(os.environ.get('SFX_PARITY_STEP', 'billing_pytest')) as connection:
        ladder = Ladder(connection)
        results = [ladder.compare(**entry) for entry in ENTRIES]
    if os.environ.get('SFX_PARITY_OUTPUT'):
        Path(os.environ['SFX_PARITY_OUTPUT']).write_text(json.dumps(results, indent=2, default=str) + '\n')
    return {result['name']: result for result in results}


@pytest.mark.parametrize('name', [entry['name'] for entry in ENTRIES])
def test_live_parity(name, live_results):
    assert_parity([live_results[name]])


def test_fail_closed():
    with pytest.raises(AssertionError, match='No relations'):
        assert_parity([])
    with pytest.raises(AssertionError, match='INVOICE_HDR'):
        assert_parity([{'name': 'INVOICE_HDR', 'passed': False}])


@pytest.mark.parametrize('name', ['x; DROP TABLE y', 'a.b', 'a"b', '', '1id'])
def test_identifiers_reject_sql(name):
    with pytest.raises(ValueError):
        identifier(name)


def test_qualified_relations_only():
    assert relation('db.schema.table') == '"DB"."SCHEMA"."TABLE"'
    with pytest.raises(ValueError):
        relation('table')


def test_padding_is_not_normalized():
    ladder = Ladder(None)
    columns = [('ID', 'NUMBER(38,0)'), ('VALUE', 'VARCHAR(10)')]
    responses = iter([columns, columns, [(1,)], [(1,)],
                      [(0, 1, 1, 1, 0, 'pro', 'pro', 1)],
                      [(0, 1, 1, 1, 0, 'pro ', 'pro ', 1)],
                      [(2,)], [(1,)], [(1, 'pro')], [(1, 'pro ')]])
    ladder.query = lambda sql, parameters=None: next(responses)
    result = ladder.compare('padding', 'db.before.t', 'db.after.t', ['ID'])
    assert result['count_passed']
    assert result['profile_mismatched_columns'] == 1
    assert result['hash_difference'] == 2
    assert result['sample_diffs'][0]['after'] == [(1, 'pro ')]
    assert not result['passed']


def test_multiset_multiplicity_is_in_hash_sql():
    sql = []
    ladder = Ladder(None)
    responses = iter([[('ID', 'NUMBER(38,0)')]] * 2 + [[(2,)], [(1,)],
                     [(0, 1, 1, 1)], [(0, 1, 1, 1)], [(1,)], [(1,)],
                     [(1,), (1,)], [(1,)]])

    def query(statement, parameters=None):
        sql.append(statement)
        return next(responses)

    ladder.query = query
    result = ladder.compare('duplicates', 'db.before.t', 'db.after.t', ['ID'])
    assert 'COUNT(*) AS _n' in sql[6]
    assert 'ABS(COALESCE(b._n,0)-COALESCE(a._n,0))' in sql[6]
    assert not result['passed']


def test_report_rejects_missing_relation_or_changed_count():
    with pytest.raises(ValueError, match='nonempty'):
        table([], [])
    with pytest.raises(ValueError, match='same nonempty'):
        table([{'name': 'invoice'}], [{'name': 'payment'}])
    with pytest.raises(ValueError, match='baseline row count changed'):
        table([{'name': 'invoice', 'before_count': 2}], [{'name': 'invoice', 'before_count': 1}])


def test_promotion_inventory_is_billing_only():
    spec = importlib.util.spec_from_file_location('billing_promote', ROOT / 'billing/promote.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    objects = module.inventory_objects()
    assert len(objects) == len({(kind, name) for kind, name, _, _ in objects})
    assert all(kind in ('table', 'view', 'macro', 'procedure', 'bteq') for kind, _, _, _ in objects)
    assert all(name.startswith('SFX_BILLING.') if kind != 'bteq'
               else source.startswith('warehouse/teradata/scripts/billing/')
               for kind, name, source, _ in objects)
    assert any(name.startswith('SFX_BILLING.STG_') for _, name, _, _ in objects)
