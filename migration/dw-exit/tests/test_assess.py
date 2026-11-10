import copy
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import assess
import check


@pytest.fixture(scope='module')
def estate():
    return assess.build()


def test_sql_parser():
    text = '-- CREATE TABLE FAKE.X (a INT);\nCREATE SET TABLE SFX_A.T (a INT);\nREPLACE VIEW SFX_A.V AS SELECT * FROM SFX_A.T;'
    parsed = assess.ddl_objects(text)
    assert [(k, n) for k, n, t in parsed] == [('table', 'SFX_A.T'), ('view', 'SFX_A.V')]
    assert assess.sql_refs(parsed[1][2]) == ({'SFX_A.T'}, set())
    assert assess.sql_refs('INSERT INTO SFX_A.T SELECT * FROM SFX_A.S JOIN SFX_A.Q ON 1=1;') == ({'SFX_A.S', 'SFX_A.Q'}, {'SFX_A.T'})
    assert assess.ddl_objects('') == []
    assert assess.sql_refs('') == (set(), set())
    assert assess.loc('-- comment\n/* two\nlines */\nSELECT 1;\n') == 1


def test_counts_and_xml(estate):
    from collections import Counter
    counts = Counter(r['kind'] for r in estate['artifacts'])
    assert {k: counts[k] for k in ['bteq', 'macro', 'procedure', 'fastload', 'tpt', 'mapping', 'session', 'worklet', 'workflow', 'catalog']} == dict(bteq=25, macro=6, procedure=4, fastload=22, tpt=20, mapping=20, session=20, worklet=1, workflow=3, catalog=6)
    assert counts['table'] + counts['view'] + counts['macro'] + counts['procedure'] + counts['catalog'] == 111
    mapping = next(r for r in estate['objects'] if r['name'] == 'm_SFX_GL_JOURNAL_LINE')
    assert mapping['target_type'] == 'snowpark'
    assert mapping['risk'] == 'high'
    assert any(r['name'] == 'm_SFX_DOC_SHARE' and r['target_type'] == 'snowpark' for r in estate['objects'])


def test_dead_and_setup(estate):
    assert estate['dead'] == ['SFX_AUDIT.AUDIT_EVENT_ARCHIVE', 'SFX_AUDIT.M_ARCHIVE_OVERVIEW', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG', 'SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_USERS.USER_PREF', 'SFX_USERS.V_USER_SETTINGS']
    assert set(estate['dead']).isdisjoint(estate['setup_only'])
    assert 'SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG' in estate['setup_only']
    assert all(r['target_type'] == 'retire' for r in estate['objects'] if r['name'] in estate['dead'])
    register = json.loads((assess.ROOT / 'demos/app/complexity/sfx-teradata.json').read_text())
    assert len(register['retire_candidates']) == len(estate['dead'])


def test_consumers(estate):
    consumers = estate['consumers']
    assert len(consumers) == 10
    hidden = {r['account'] for r in consumers if r['hidden']}
    assert hidden == {'FIN_ANALYST_JMORALES', 'nb_dsci_pkhan'}
    for user in hidden:
        assert estate['scans'][user] == {'warehouse_etl_hits': [], 'repo_hits': []}
    assert not estate['scans']['svc_partner_sftp']['warehouse_etl_hits']
    assert estate['scans']['svc_partner_sftp']['repo_hits']
    finance = next(r for r in consumers if r['account'] == 'nb_finance_analysis')
    assert finance['applications'] == []
    assert sum(bool(r['applications']) for r in consumers if not r['hidden']) == 7


def test_dependency_order(estate):
    objects = {r['id']: r for r in estate['objects']}
    assert all(objects[a]['wave'] <= objects[b]['wave'] for a, b in estate['dependencies'])


def test_missing_outputs(tmp_path):
    errors = check.validate(tmp_path, source=False)
    assert 'missing: inventory.csv' in errors


def test_generated_check():
    assert check.validate() == []


@pytest.mark.parametrize('fault', ['duplicate', 'enum', 'dead', 'lineage', 'board', 'wave'])
def test_validator_rejects(tmp_path, fault):
    import shutil
    for name in ['inventory.csv', 'inventory.md', 'lineage.md', 'manifest.yaml', 'plan.md', 'board/README.md', 'board/board.json', 'README.md']:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(assess.OUT / name, dest)
    path = tmp_path / 'manifest.yaml'
    manifest = yaml.safe_load(path.read_text())
    if fault == 'duplicate':
        manifest['objects'].append(copy.deepcopy(manifest['objects'][0]))
    elif fault == 'enum':
        manifest['objects'][0]['target_type'] = 'invalid'
    elif fault == 'dead':
        next(r for r in manifest['objects'] if r['name'] in manifest['dead'])['target_type'] = 'dbt_model'
    elif fault == 'lineage':
        (tmp_path / 'lineage.md').write_text('flowchart LR')
    elif fault == 'board':
        board_path = tmp_path / 'board/board.json'
        data = json.loads(board_path.read_text())
        data['waves']['1']['total'] += 1
        board_path.write_text(json.dumps(data))
    elif fault == 'wave':
        a, b = manifest['dependencies'][0]
        for r in manifest['objects']:
            if r['id'] == a:
                r['wave'] = 4
            if r['id'] == b:
                r['wave'] = 1
    path.write_text(yaml.safe_dump(manifest))
    assert check.validate(tmp_path, source=False)
