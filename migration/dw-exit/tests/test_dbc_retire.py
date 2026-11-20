import pytest

from parity import dbc_retire as dbc


@pytest.fixture(scope='module')
def database():
    db = dbc.materialize()
    yield db
    db.close()


@pytest.mark.parametrize('name', ['DBC_QRYLOG','DBC_QRYLOGOBJECTS','DBC_TABLESV','QRYLOGV','QRYLOGOBJECTSV','TABLESV'])
def test_catalog_evidence_and_real_mismatches(database, name, monkeypatch):
    obj = {'name': 'DBC.'+name, 'kind': 'catalog'}
    proof = dbc.evidence(obj, [])
    assert proof['passed'] and proof['window_reads']==(2 if name.startswith('DBC_') else 1)
    assert proof['last_read_matches_snapshot']
    monkeypatch.setattr(dbc, 'emulator', lambda *args: {'status':'red','reason':'not requested in unit test'})
    result = dbc.measure(obj, database, [])
    query_log = name in ('DBC_QRYLOG','QRYLOGV')
    assert result['status']==('red' if query_log else 'approved_deviation')
    assert result['snowflake']=='red'
    assert result['keyed_row_hash']['difference']>0
    if query_log:
        assert result['reason'].startswith('Differences outside approved missing-field scope')
    assert result['owner_decision']['status'] == 'approved'
    assert result['owner_decision']['scope_valid'] is (not query_log)
    if not query_log:
        assert result['owner_decision']['excluded_source_rows'] == (810 if 'QRYLOGOBJECT' in name else 10)
    assert result['mapped_columns_parity']['passed']
    assert result['consumer_parity']['passed'] is False
    assert result['consumer_mapped_columns_parity']['passed']
    assert dbc.evidence(obj, [{'file':'services/caller.sql'}])['passed'] is False


def test_empty_reads_fail_closed(monkeypatch):
    monkeypatch.setattr(dbc, 'reads', lambda *args: [])
    assert not dbc.evidence({'name':'DBC.TABLESV','kind':'catalog'}, [])['passed']


def test_corrupt_feed_is_not_silently_green(monkeypatch, tmp_path):
    monkeypatch.setattr(dbc, 'ROOT', tmp_path)
    with pytest.raises(Exception):
        dbc.materialize()


def test_no_application_callers():
    assert dbc.callers()==[]


def test_tooling_callers_are_not_hidden():
    files = {hit['file'] for hit in dbc.callers(('warehouse', 'scripts'))}
    assert 'warehouse/exit/reads.py' in files
    assert 'warehouse/teradata/dbql/consumer_reads.bteq' in files
    assert 'warehouse/teradata/bteq/runner.py' in files


def test_writes_are_preserved(database):
    assert database.execute("SELECT COUNT(*) FROM DBC.DBC_QRYLOGOBJECTS WHERE UsageType='WRITE'").fetchone()==database.execute("SELECT COUNT(*) FROM COMPAT.DBC_QRYLOGOBJECTS WHERE UsageType='WRITE'").fetchone()


def test_empty_and_mismatched_mapped_ladder(database):
    db = database
    db.execute('BEGIN')
    try:
        db.execute('DELETE FROM DBC.DBC_QRYLOGOBJECTS')
        db.execute('DELETE FROM ACCOUNT_USAGE.ACCESS_HISTORY')
        assert dbc.mapped_compare(db, 'DBC_QRYLOGOBJECTS')['passed']
        db.execute("INSERT INTO DBC.DBC_QRYLOGOBJECTS VALUES (1,'X','Y','T','WRITE')")
        assert not dbc.mapped_compare(db, 'DBC_QRYLOGOBJECTS')['passed']
    finally:
        db.execute('ROLLBACK')


def test_provenance_has_exact_ranges(database, monkeypatch):
    monkeypatch.setattr(dbc, 'emulator', lambda *args: {})
    obj = {'name':'DBC.QRYLOGV','kind':'catalog'}
    row = {**obj, 'subject_area':'dbc', **dbc.measure(obj, database, [])}
    text = dbc.markdown([row])
    assert 'devin/sfg1120-integration/' in text
    assert '10_account_usage.sql#L' in text
    assert 'ladder.py#L' in text
    assert 'inventory.csv#L' in text
    assert 'sfx1119' not in text
    assert row['snowflake_reason'] == 'Snowflake login down; no connection attempted (sfg1120)'
    assert all('devin/sfg1120-integration/' in item['url'] for item in row['metric_evidence'].values())


@pytest.mark.parametrize('external',[False,True])
def test_only_missing_fields_use_generic_approved_deviation(database,monkeypatch,external):
    monkeypatch.setattr(dbc,'emulator',lambda *args:{})
    database.execute('BEGIN')
    try:
        database.execute('''CREATE OR REPLACE VIEW COMPAT.QRYLOGV AS
            SELECT * REPLACE (CAST(NULL AS INTEGER) AS ProcID, CAST(NULL AS VARCHAR) AS ClientID,
                              CAST(NULL AS DECIMAL(14,6)) AS AMPCPUTime,
                              CAST(NULL AS BIGINT) AS TotalIOCount) FROM DBC.QRYLOGV''')
        row = dbc.measure({'name':'DBC.QRYLOGV','kind':'catalog'},database,
                          [{'file':'services/caller.sql'}] if external else [])
        assert row['status']==('red' if external else 'approved_deviation')
        assert row['owner_decision']['scope_valid']
        assert row['keyed_row_hash']['difference']>0
        assert row['snowflake']=='red'
    finally:
        database.execute('ROLLBACK')
