import json

import duckdb
import pytest

import assess
from parity import object_board, pc_users
from test_users import tables


def inputs(db):
    tables(db)
    db.execute('ALTER TABLE USERS.LOGIN_EVENT ALTER COLUMN LOGIN_TS TYPE TIMESTAMP')
    db.execute('CREATE SCHEMA INPUT')
    for table in pc_users.TABLES:
        db.execute('CREATE TABLE INPUT.'+table+' AS SELECT * FROM USERS.'+table)


@pytest.mark.parametrize('populated',[False,True])
def test_shipped_models_empty_and_normalized_replacement(populated):
    with duckdb.connect() as db:
        inputs(db)
        db.execute("INSERT INTO USERS.STG_APP_USER VALUES (2,'stale','stale',NULL,NULL)")
        db.execute("INSERT INTO USERS.ROLE_GRANT VALUES (2,2,'stale',NULL)")
        if populated:
            db.execute("INSERT INTO INPUT.APP_USER VALUES (1,' Name ',' Mixed@EXAMPLE ',' active ','2020-01-01')")
            db.execute("INSERT INTO INPUT.ROLE_GRANT VALUES (1,1,' owner ','2020-01-01')")
        pc_users.execute_model(db,'STG_APP_USER')
        pc_users.execute_model(db,'ROLE_GRANT')
        assert db.execute('SELECT USER_ID,DISPLAY_NAME,EMAIL,STATUS_CD FROM USERS.STG_APP_USER').fetchall() == ([(1,'Name','mixed@example','ACTIVE')] if populated else [])
        assert db.execute('SELECT GRANT_ID,ROLE_CD FROM USERS.ROLE_GRANT').fetchall() == ([(1,'OWNER       ')] if populated else [])


def test_shipped_router_drops_default_and_merge_preserves_old_rows():
    with duckdb.connect() as db:
        inputs(db)
        db.execute("INSERT INTO USERS.LOGIN_EVENT VALUES (8,8,NULL,'OLD','WEB')")
        db.execute("INSERT INTO USERS.LOGIN_EVENT VALUES (1,9,NULL,'OLD','WEB')")
        db.execute("INSERT INTO INPUT.LOGIN_EVENT VALUES (1,1,'2026-11-09','success','web'),(2,1,'2026-11-09','failed','web'),(3,1,'2026-11-09','locked','web'),(4,1,'2026-11-09','mfa_failed','web'),(5,1,'2026-11-09','OTHER','web')")
        pc_users.execute_model(db,'LOGIN_EVENT')
        assert db.execute('SELECT LOGIN_ID FROM USERS.LOGIN_EVENT ORDER BY 1').fetchall() == [(1,),(2,),(3,),(4,),(8,)]
        assert db.execute('SELECT USER_ID FROM USERS.LOGIN_EVENT WHERE LOGIN_ID=1').fetchone() == (1,)


def test_app_user_dbt_merge_is_isolated_and_retains_unmatched_rows():
    with duckdb.connect() as db:
        inputs(db)
        db.execute("INSERT INTO USERS.APP_USER VALUES (1,'old',NULL,NULL,NULL),(9,'keep',NULL,NULL,NULL)")
        db.execute("INSERT INTO INPUT.STG_APP_USER VALUES (1,'changed','mail','ACTIVE','2020-01-01'),(2,'new','mail','ACTIVE','2020-01-01')")
        pc_users.execute_model(db,'APP_USER')
        assert db.execute('SELECT USER_ID,DISPLAY_NAME FROM USERS.APP_USER ORDER BY 1').fetchall() == [(1,'changed'),(2,'new'),(9,'keep')]


@pytest.mark.parametrize('populated',[False,True])
def test_team_member_shipped_unicode_macro_and_merge(populated):
    with duckdb.connect() as db:
        inputs(db)
        if populated:
            db.execute("INSERT INTO INPUT.TEAM_MEMBER VALUES (1,1,1,'straße','2020-01-01')")
        pc_users.execute_model(db,'TEAM_MEMBER')
        assert db.execute('SELECT ROLE_CD FROM USERS.TEAM_MEMBER').fetchall() == ([('STRASSE     ',)] if populated else [])


def test_model_execution_error_is_not_a_green_result():
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA USERS')
        with pytest.raises(duckdb.Error):
            pc_users.execute_model(db,'LOGIN_EVENT')


def test_pc_evidence_scope_and_checksum_fail_closed(tmp_path,monkeypatch):
    path = tmp_path/'capture.json'
    path.write_text(json.dumps(dict(returncode=0,run_token='wrong',namespace='n',business_date='20261109')))
    with pytest.raises(ValueError,match='scope differs'):
        pc_users.proofs('n',tmp_path,'20261109',tmp_path)
    data = dict(returncode=0,run_token=object_board.RunConfig.from_env().token,namespace='n',business_date='20261109',inputs={},capture_sha256='wrong')
    path.write_text(json.dumps(data))
    (tmp_path/'capture.duckdb').write_text('changed')
    monkeypatch.setattr(pc_users,'fingerprint',lambda *a:{})
    with pytest.raises(ValueError,match='checksum differs'):
        pc_users.proofs('n',tmp_path,'20261109',tmp_path)
    monkeypatch.setattr(pc_users,'fingerprint',lambda *a:{'new':'hash'})
    with pytest.raises(ValueError,match='inputs changed'):
        pc_users.proofs('n',tmp_path,'20261109',tmp_path)


@pytest.mark.parametrize('status',['green','red'])
def test_ten_pc_rows_use_own_proof_and_app_user_stays_stopped(status):
    objects = [o for o in assess.build()['objects'] if o['subject_area']=='users' and o['kind'] in ('mapping','session')]
    measurement = dict(row_count={'before':0,'after':0},column_profile={},keyed_row_hash={'difference':0},sampled_differences=[],comparison_rules={}) if status == 'green' else None
    proofs = {mapping:dict(status=status,reason=None if status == 'green' else 'PC execution failed',measurement=measurement) for mapping in pc_users.MAPPINGS}
    board = object_board.build_board({'objects':objects},pc_results=proofs)
    assert len(board['rows']) == 10
    for row in board['rows']:
        assert row['local_duckdb'] == ('red' if row['name'].endswith('m_SFX_APP_USER') else status)
        assert row['snowflake'] == 'red'
        assert row['bteq_relation_measurement']['row_count'] is None
        assert row['row_count'] == (None if status == 'red' else measurement['row_count'])
        assert row['powercenter']['status'] == status
        if status == 'green' and row['name'].endswith('m_SFX_APP_USER'):
            assert 'APP_USER display-name truncation decision' in row['reason']
            assert 'hash_difference=0' in row['reason']
            assert 'mismatch' not in row['reason']
        p = row['provenance']
        links = [entry for entries in p['converted'].values() for entry in entries]
        assert any('warehouse/dbt/models/pc/content/' in link['file'] for link in links)
        assert all('devin/sfg1120-users' in link['url'] for link in links)
