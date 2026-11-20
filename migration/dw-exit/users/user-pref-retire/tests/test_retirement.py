from pathlib import Path
import sys

import duckdb
import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import hook
import retirement


def test_hook_keeps_all_four_rows_red():
    board = retirement.board
    manifest = yaml.safe_load((retirement.ROOT / 'migration/dw-exit/manifest.yaml').read_text())
    manifest = board.select_group(manifest, board.load_group(HERE))
    before = duckdb.connect()
    before.execute('CREATE SCHEMA SFX_USERS')
    names = {'SFX_' + name for name in hook.OUTPUTS}
    for name in names:
        before.execute('CREATE TABLE ' + board.relation(name) + ' (ID INTEGER)')
        before.execute('INSERT INTO ' + board.relation(name) + ' VALUES (1)')
    after, ready, errors = board.materialize(before, names, HERE, ('USERS',))
    try:
        assert not ready
        assert after.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='USERS'").fetchone()[0] == 0
        payload = board.build_board(manifest, before, after, ready, errors)
        assert len(payload['rows']) == 4
        assert all(row['status'] == 'red' and row['reason'] == hook.REASON for row in payload['rows'])
    finally:
        before.close()
        after.close()


def test_empty_hook():
    after = duckdb.connect()
    after.execute('CREATE SCHEMA USERS')
    ready, errors = set(), {}
    hook.materialize(None, after, ready, errors)
    assert not ready
    assert errors == dict.fromkeys(hook.OUTPUTS, hook.REASON)
    after.close()


def test_group_dependencies():
    manifest = yaml.safe_load((retirement.ROOT / 'migration/dw-exit/manifest.yaml').read_text())
    lineage = (retirement.ROOT / 'migration/dw-exit/lineage.md').read_text()
    for obj in board_objects(manifest):
        assert retirement.dependency_check(manifest, obj['id'], lineage)['pass']


def board_objects(manifest):
    return retirement.board.select_group(manifest, retirement.board.load_group(HERE))['objects']


@pytest.mark.parametrize('target_type,passed', [('retire', True), ('dbt_model', False)])
def test_dependency_detects_live_reader(target_type, passed):
    manifest = {'objects': [{'id': 'a', 'kind': 'table', 'name': 'SFX_USERS.USER_PREF'},
                            {'id': 'b', 'kind': 'view', 'name': 'reader', 'target_type': target_type}],
                'dependencies': [('a', 'b')]}
    assert retirement.dependency_check(manifest, 'a', '')['pass'] is passed
    assert retirement.dependency_check(manifest, 'b', '')['pass']
