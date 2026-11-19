import importlib.util
import json
from pathlib import Path
import sys

import duckdb
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('object_board', ROOT/'migration/dw-exit/parity/object_board.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)
from parity import local_documents
from parity.provenance import markdown

CONVERSION = ROOT/'migration/dw-exit/documents'
OBJECTS = [o for o in yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())['objects'] if o['subject_area'] == 'documents']


def named(*names):
    return [o for o in OBJECTS if o['name'] in names]


def test_scope_is_59_objects_with_four_retirements():
    assert len(OBJECTS) == 59
    assert sorted(o['name'] for o in OBJECTS if o['target_type'] == 'retire') == [
        'SFX_DOCUMENTS.SEARCH_INDEX_LOG', 'SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG', 'SFX_DOCUMENTS.V_SEARCH_HISTORY', 'documents_search_index_log']


def test_conversion_files_cover_every_teradata_object():
    tables = [s[0] for s in local_documents.sections(CONVERSION/'00_tables.sql', r'^CREATE OR REPLACE TABLE \S+\.DOCUMENTS\.(\w+) \($')]
    stage = [s[0] for s in local_documents.sections(CONVERSION/'05_stage.sql', r'^-- (documents_\w+)\.tpt$')]
    loads = [s[0] for s in local_documents.sections(CONVERSION/'10_load.sql', r'^-- (\d\d_\w+)\.bteq$')]
    convert = [o for o in OBJECTS if o['system'] == 'teradata' and o['target_type'] != 'retire']
    assert sorted(tables) == sorted(o['name'].split('.')[1] for o in convert if o['kind'] == 'table')
    assert sorted(stage) == sorted(o['name'] for o in convert if o['kind'] == 'tpt')
    assert sorted(loads+['10_storage_monthly']) == sorted(o['name'] for o in convert if o['kind'] == 'bteq')
    assert not any('SEARCH' in name for name in tables+stage)


def test_owner_decisions_are_not_resolved_in_code():
    load = (CONVERSION/'10_load.sql').read_text()
    assert 'DISTINCT' not in load.upper().replace('-- SNOWFLAKE KEEPS THEM; NO DISTINCT IS ADDED', '')
    assert 'ORDER BY VERSION_TS DESC) = 1' in load
    share = (ROOT/'warehouse/dbt/models/pc/content/pc_content__doc_share.sql').read_text().lower()
    assert 'row_number' not in share and 'qualify' not in share


@pytest.fixture
def estate(tmp_path, monkeypatch):
    before, after = duckdb.connect(), duckdb.connect()
    before.execute('CREATE SCHEMA SFX_DOCUMENTS')
    for table in ('STG_STORAGE_USAGE_DAILY', 'STORAGE_USAGE_DAILY'):
        before.execute(f'CREATE TABLE SFX_DOCUMENTS.{table} (STORAGE_USAGE_ID BIGINT, CUSTOMER_ID BIGINT, OWNER_USER_ID BIGINT, USAGE_DT DATE, BYTES_USED BIGINT, OBJECT_COUNT INTEGER)')
    for table in ('STG_FOLDER', 'FOLDER'):
        before.execute(f'CREATE TABLE SFX_DOCUMENTS.{table} (FOLDER_ID BIGINT, OWNER_USER_ID BIGINT, CUSTOMER_ID BIGINT, FOLDER_NAME VARCHAR, CREATED_DT DATE)')
    for table in ('STG_DOCUMENT', 'DOCUMENT'):
        before.execute(f'CREATE TABLE SFX_DOCUMENTS.{table} (DOCUMENT_ID BIGINT, FOLDER_ID BIGINT, OWNER_USER_ID BIGINT, CUSTOMER_ID BIGINT, DOCUMENT_NAME VARCHAR, CREATED_DT DATE, STATUS_CD VARCHAR, FILE_TYPE VARCHAR)')
    for table in ('STG_COLLAB_SESSION', 'COLLAB_SESSION'):
        before.execute(f'CREATE TABLE SFX_DOCUMENTS.{table} (SESSION_ID BIGINT, DOCUMENT_ID BIGINT, USER_ID BIGINT, START_TS TIMESTAMP, END_TS TIMESTAMP)')
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY VALUES (1,7,3,DATE '2026-11-01',10,2),(1,7,3,DATE '2026-11-01',10,2)")
    before.execute("INSERT INTO SFX_DOCUMENTS.STORAGE_USAGE_DAILY VALUES (1,7,3,DATE '2026-11-01',10,2)")
    for table in ('STG_FOLDER', 'FOLDER'):
        before.execute(f"INSERT INTO SFX_DOCUMENTS.{table} VALUES (1,3,7,'Plans',DATE '2026-01-02')")
    files = {'STORAGE_USAGE_DAILY': '1|7|3|2026-11-01|10|2\n1|7|3|2026-11-01|10|2\n', 'FOLDER': '1|3|7|Plans|2026-01-02\n', 'DOCUMENT': '', 'COLLAB_SESSION': ''}
    for table, text in files.items():
        (tmp_path/'documents'/table).mkdir(parents=True)
        (tmp_path/'documents'/table/'20261109.psv').write_text(text)
    monkeypatch.setenv('LANDING_DIR', str(tmp_path))
    monkeypatch.setenv('RUN_TOKEN', 'sfx1119')
    objects = named('SFX_DOCUMENTS.FOLDER', 'SFX_DOCUMENTS.STG_FOLDER', 'documents_folder', '01_load_folders',
                    'SFX_DOCUMENTS.STORAGE_USAGE_DAILY', 'SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY')
    results = {}
    local_documents.teradata(before, after, 'host=127.0.0.1 port=1 connect_timeout=1', '20261109', results, {o['id']: o for o in objects})
    yield before, after, objects, results
    before.close()
    after.close()


def test_shipped_sql_runs_and_set_table_stays_red(estate):
    before, after, objects, results = estate
    for obj in objects:
        if obj['name'] == 'SFX_DOCUMENTS.STORAGE_USAGE_DAILY':
            results[obj['id']]['owner_decision'] = {'id': 'set_table_dedupe', 'question': local_documents.OWNER_DECISIONS['set_table_dedupe'][0]}
    rows = {r['name']: r for r in board.build_board({'objects': objects}, before, after, set(), documents=results)['rows']}
    for name in ('SFX_DOCUMENTS.FOLDER', 'SFX_DOCUMENTS.STG_FOLDER', 'documents_folder', '01_load_folders', 'SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY'):
        assert rows[name]['status'] == 'green', (name, rows[name]['reason'])
        assert rows[name]['snowflake'] == 'red'
    usage = rows['SFX_DOCUMENTS.STORAGE_USAGE_DAILY']
    assert usage['status'] == 'red' and usage['row_count'] == {'before': 1, 'after': 2}
    assert usage['measured_parity'] == 'mismatch' and usage['sampled_differences']
    assert usage['reason'].startswith('open owner decision')


def test_owner_decision_stays_red_when_measured_equal(estate):
    before, after, objects, results = estate
    folder = next(o for o in objects if o['name'] == 'SFX_DOCUMENTS.FOLDER')
    results[folder['id']]['owner_decision'] = {'id': 'x', 'question': 'undecided'}
    row = board.build_board({'objects': [folder]}, before, after, set(), documents=results)['rows'][0]
    assert row['measured_parity'] == 'match' and row['status'] == 'red' and row['local_duckdb'] == 'red'


def test_rows_click_through_to_existing_lines(estate):
    before, after, objects, results = estate
    rows = board.build_board({'objects': objects}, before, after, set(), documents=results)['rows']
    for row in rows:
        links = row['provenance']['source']+row['provenance']['converted']['documents']+list(row['provenance']['metrics'].values())
        assert row['provenance']['source'] and row['provenance']['converted']['documents']
        for item in links:
            lines = (ROOT/item['file']).read_text().splitlines()
            assert 1 <= item['start_line'] <= item['end_line'] <= len(lines)
            assert item['url'].endswith(f"{item['file']}#L{item['start_line']}-L{item['end_line']}")
    text = markdown(rows)
    assert '## Documents parity provenance' in text and 'migration/dw-exit/documents/10_load.sql' in text


def test_retirement_needs_query_log_confirmation():
    results = {}
    local_documents.retirement(OBJECTS, results)
    by_name = {o['name']: results[o['id']] for o in OBJECTS if o['id'] in results}
    assert len(by_name) == 4
    blocked = by_name.pop('SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG')
    assert blocked['retire']['reads'] == 1 and blocked['retire']['readers'][0]['UserName'] == 'svc_report_recon'
    assert blocked['reason'].startswith('retirement blocked')
    assert all(entry['retire']['reads'] == 0 for entry in by_name.values())
    rows = board.build_board({'objects': named(*by_name, 'SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG')}, duckdb.connect(), duckdb.connect(), set(),
                             documents={**results})['rows']
    assert all(row['status'] == 'red' and row['retire'] for row in rows)


def test_unmeasured_powercenter_and_spark_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('PC_SOURCE_DSN', 'host=127.0.0.1 port=1 connect_timeout=1')
    results = {}
    local_documents.powercenter(duckdb.connect(), duckdb.connect(), '20261109', results, {o['id']: o for o in OBJECTS})
    assert len(results) == 6 and all(r['reason'].startswith('PowerCenter leg not measured') for r in results.values())
    spark = {}
    local_documents.spark(duckdb.connect(), duckdb.connect(), OBJECTS, 'none', spark)
    assert len(spark) == 13 and all(not r['pairs'] and r['reason'] for r in spark.values())


def test_committed_board_keeps_decisions_and_snowflake_red():
    rows = [r for r in json.loads((ROOT/'migration/dw-exit/board/board.json').read_text())['rows'] if r['subject_area'] == 'documents']
    assert len(rows) == 59 and all(r['snowflake'] == 'red' for r in rows)
    decided = {r['name'] for r in rows if r.get('owner_decision')}
    assert {'SFX_DOCUMENTS.STORAGE_USAGE_DAILY', '02_current_versions', 'm_SFX_DOC_SHARE'} <= decided
    assert all(r['status'] == 'red' for r in rows if r.get('owner_decision') or r.get('retire'))
