import importlib.util
from pathlib import Path
from types import SimpleNamespace

from defusedxml import ElementTree
import duckdb
import pytest
import yaml

from parity import local_content, object_board, provenance

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('content_convert', ROOT/'migration/dw-exit/content/convert.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


@pytest.fixture
def db():
    connection = duckdb.connect()
    folder = ElementTree.parse(ROOT/local_content.XML).find('.//FOLDER')
    for schema in ('USERS', 'DOCUMENTS', 'PC_SRC'):
        connection.execute('CREATE SCHEMA ' + schema)
    for target in folder.findall('TARGET'):
        name = target.get('NAME')
        schema = 'DOCUMENTS' if name in compiler.DOCUMENTS else 'USERS'
        columns = []
        for field in target.findall('TARGETFIELD'):
            kind = field.get('DATATYPE').upper()
            if kind in ('CHAR', 'VARCHAR'):
                kind = 'VARCHAR'
            columns.append(field.get('NAME') + ' ' + kind)
        connection.execute('CREATE TABLE ' + schema + '.' + name + ' (' + ', '.join(columns) + ')')
    for name, (_, source) in local_content.LANDING.items():
        connection.execute('CREATE TABLE PC_SRC.' + name + ' AS SELECT * FROM ' + source.removeprefix('SFX_') + ' WHERE FALSE')
    connection.execute("INSERT INTO USERS.TEAM_MEMBER VALUES (7,8,9,'MEMBER',DATE '2026-11-09')")
    yield connection
    connection.close()


def seed(db):
    db.execute("INSERT INTO PC_SRC.APP_USER VALUES (1,?, ' A@EXAMPLE.COM ', ' active ',DATE '2026-11-09')", ['x'*78])
    db.execute("INSERT INTO PC_SRC.ROLE_GRANT VALUES (1,1,'admin',DATE '2026-11-09')")
    db.execute("INSERT INTO PC_SRC.LOGIN_EVENT VALUES (1,1,TIMESTAMP '2026-11-09 12:00:00','SUCCESS','WEB'),"
               "(1,1,TIMESTAMP '2026-11-09 13:00:00','FAILED','API'),"
               "(2,1,TIMESTAMP '2026-11-09 14:00:00','OTHER','API')")
    db.execute("INSERT INTO PC_SRC.DOCUMENT VALUES (1,1,1,1,'test',DATE '2026-11-09','ACTIVE','PDF')")
    db.execute("INSERT INTO PC_SRC.DOC_SHARE VALUES (1,1,1,'VIEW',DATE '2026-11-09')")


def test_generated_procedure_is_owned_selects_and_matches_xml():
    assert compiler.generate() == local_content.PROCEDURE.read_text()
    text = compiler.generate()
    assert 'LANGUAGE SQL' in text and 'OPS.WF_SFX_CONTENT_DAILY()' in text
    assert 'EXCEPTION' not in text
    for name in compiler.STEPS:
        assert 'CALL '+compiler.session_target(name)+'();' in text
        area = 'documents' if name in compiler.DOCUMENTS else 'users'
        assert compiler.select(name) in compiler.generate_sessions(area)
        assert compiler.generate_sessions(area) == (ROOT/'migration/dw-exit'/area/'52_sessions.sql').read_text()
    flow = ElementTree.parse(ROOT/local_content.XML).find('.//WORKFLOW')
    enabled = {t.get('NAME').removeprefix('s_m_SFX_') for t in flow.findall('TASKINSTANCE')
               if t.get('TASKTYPE') == 'Session' and t.get('ISENABLED') == 'YES'}
    assert enabled == set(compiler.STEPS)
    position = {name: i for i, name in enumerate(compiler.STEPS)}
    for edge in flow.findall('WORKFLOWLINK'):
        parent, child = [edge.get(key).removeprefix('s_m_SFX_') for key in ('FROMTASK', 'TOTASK')]
        if parent in enabled and child in enabled:
            assert position[parent] < position[child]
    assert len(list(local_content.statements())) == 10


def test_typed_session_writes_routes_truncation_and_rerun(db):
    seed(db)
    db.execute("INSERT INTO USERS.STG_APP_USER VALUES (99,'stale','stale','OLD',NULL)")
    db.execute("INSERT INTO USERS.APP_USER VALUES (1,'old','old','OLD',NULL),(99,'retained','old','OLD',NULL)")
    db.execute("INSERT INTO USERS.ROLE_GRANT VALUES (99,99,'OLD',NULL)")
    db.execute("INSERT INTO USERS.LOGIN_EVENT VALUES (1,1,NULL,'OLD','OLD')")
    local_content.execute(db)
    assert db.execute('SELECT USER_ID,LENGTH(DISPLAY_NAME) FROM USERS.STG_APP_USER').fetchall() == [(1,78)]
    assert db.execute('SELECT LENGTH(DISPLAY_NAME) FROM USERS.APP_USER WHERE USER_ID=1').fetchone() == (60,)
    assert db.execute('SELECT USER_ID FROM USERS.APP_USER ORDER BY 1').fetchall() == [(1,),(99,)]
    assert db.execute('SELECT GRANT_ID FROM USERS.ROLE_GRANT').fetchall() == [(1,)]
    login = db.execute('SELECT LOGIN_ID,USER_ID,RTRIM(RESULT_CD) FROM USERS.LOGIN_EVENT').fetchall()
    assert login == [(1,1,'FAILED')]
    assert isinstance(login[0][0], int)
    assert db.execute('SELECT RTRIM(ACCESS_LEVEL) FROM DOCUMENTS.DOC_SHARE').fetchone() == ('OWNER',)
    untouched = db.execute('SELECT * FROM USERS.TEAM_MEMBER').fetchall()
    local_content.execute(db)
    assert db.execute('SELECT COUNT(*) FROM DOCUMENTS.DOC_SHARE').fetchone() == (1,)
    assert db.execute('SELECT COUNT(*) FROM USERS.LOGIN_EVENT').fetchone() == (1,)
    assert db.execute('SELECT * FROM USERS.TEAM_MEMBER').fetchall() == untouched


def test_empty_inputs_clear_only_truncate_targets(db):
    seed(db)
    local_content.execute(db)
    for name in local_content.LANDING:
        db.execute('DELETE FROM PC_SRC.' + name)
    local_content.execute(db)
    for name in compiler.TRUNCATE:
        assert db.execute('SELECT COUNT(*) FROM ' + compiler.relation(name).split('.',1)[1]).fetchone() == (0,)
    for name in compiler.KEYS:
        assert db.execute('SELECT COUNT(*) FROM ' + compiler.relation(name).split('.',1)[1]).fetchone() == (1,)
    assert db.execute('SELECT COUNT(*) FROM USERS.TEAM_MEMBER').fetchone() == (1,)


def test_failure_blocks_downstream_without_rolling_back_prior_sessions(db):
    seed(db)
    db.execute('DROP TABLE PC_SRC.ROLE_GRANT')
    with pytest.raises(duckdb.Error):
        local_content.execute(db)
    assert db.execute('SELECT COUNT(*) FROM USERS.APP_USER').fetchone() == (1,)
    for table in ('USERS.LOGIN_EVENT', 'DOCUMENTS.STG_DOCUMENT', 'DOCUMENTS.DOCUMENT', 'DOCUMENTS.DOC_SHARE'):
        assert db.execute('SELECT COUNT(*) FROM ' + table).fetchone() == (0,)
    assert db.execute('SELECT COUNT(*) FROM USERS.TEAM_MEMBER').fetchone() == (1,)


def test_content_board_measures_all_outputs_and_links_pending_decision(db):
    seed(db)
    local_content.execute(db)
    for source in local_content.OUTPUTS:
        local_content.clone(db, db, source.removeprefix('SFX_'), source)
    db.execute('UPDATE SFX_USERS.STG_APP_USER SET DISPLAY_NAME=LEFT(DISPLAY_NAME,60)')
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    obj = next(obj for obj in manifest['objects'] if obj['name'] == 'wf_SFX_CONTENT_DAILY')
    result = object_board.build_board({'objects':[obj]}, db, db,
        {s.removeprefix('SFX_') for s in local_content.OUTPUTS})
    row = result['rows'][0]
    assert row['reason'] == local_content.PENDING
    assert row['local_duckdb'] == row['snowflake'] == 'red'
    assert len(row['relation_results']) == 8
    assert row['keyed_row_hash']['SFX_USERS.STG_APP_USER']['difference'] == 2
    assert row['sampled_differences']['SFX_USERS.STG_APP_USER'][0]['key'] == [1]
    assert all(v['passed'] for k,v in row['relation_results'].items() if k != 'SFX_USERS.STG_APP_USER')
    mapping = dict(obj, id='other-worker', name='m_SFX_STG_APP_USER', kind='mapping', subject_area='users',
                   output_relations=['SFX_USERS.STG_APP_USER'])
    scoped = object_board.build_board({'objects':[obj,mapping]},db,db,content_available=
        {s.removeprefix('SFX_') for s in local_content.OUTPUTS})['rows']
    assert scoped[0]['row_count'] is not None and scoped[1]['row_count'] is None
    p = row['provenance']
    assert len(p['decision']) == 4
    for entry in p['decision'] + p['source'] + p['converted']['procedure'] + list(p['metrics'].values()):
        assert '/devin/sfx1119-content-migration/' in entry['url'] and '#L' in entry['url']
    markdown = provenance.content_markdown([row])
    assert local_content.PENDING in markdown
    assert 'SFX_USERS.TEAM_MEMBER | 1 | 1 | match | match' in markdown


def test_source_failure_and_unsupported_inputs_are_closed(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='local emulator'):
        local_content.run_source('host=remote dbname=teradata', 'test', tmp_path, '20261109')
    with pytest.raises(ValueError, match='business date'):
        local_content.run_source('host=localhost', 'test', tmp_path, '20261110')
    monkeypatch.setattr(local_content, 'ROOT', tmp_path)
    monkeypatch.setattr(local_content.subprocess, 'run', lambda *a,**kw: SimpleNamespace(returncode=1,stdout='failed',stderr=''))
    with pytest.raises(RuntimeError, match='PowerCenter failed'):
        local_content.run_source('host=localhost', 'test', tmp_path, '20261109')
    assert (tmp_path/'migration/dw-exit/.runs/content-workflow.log').read_text() == 'failed'
    path = tmp_path/'bad.sql'
    path.write_text('SELECT 1')
    with pytest.raises(ValueError, match='wrapper'):
        list(local_content.statements(path))


def test_missing_prestate_never_marks_content_ready(db):
    ready, errors, _ = local_content.materialize(db,db,'host=localhost','test',None)
    assert not ready and len(errors) == 8
    assert all('content execution:' in message for message in errors.values())


def test_content_task_dag_preserves_both_links():
    dag = yaml.safe_load((ROOT/'warehouse/snowflake/pc_dag/content.yml').read_text())['tasks']
    assert dag['ROLE_GRANT']['after'] == ['APP_USER']
    assert dag['LOGIN_EVENT']['after'] == ['APP_USER']
    assert dag['DOC_SHARE']['after'] == ['DOCUMENT','ROLE_GRANT']
    assert dag['FINISH']['after'] == ['DOC_SHARE','LOGIN_EVENT']
    assert 'TEAM_MEMBER' not in dag
    for name in compiler.STEPS:
        assert dag[name]['sql'] == 'CALL '+compiler.session_target(name)+'()'


def test_unknown_area_session_fails_closed(tmp_path):
    path = tmp_path/'workflow.sql'
    path.write_text(compiler.generate().replace(compiler.session_target('APP_USER'), 'X.OPS.UNKNOWN'))
    with pytest.raises(ValueError, match='Unknown content session'):
        list(local_content.statements(path))


def test_manifest_users_session_targets_exist():
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    for obj in manifest['objects']:
        if obj['subject_area'] == 'users' and obj['kind'] == 'session':
            model = ROOT/'warehouse/dbt/models/users'/(obj['target']+'.sql')
            assert model.is_file()
            assert ('OPS.'+obj['target'].upper()+'()') in compiler.generate_sessions('users')
