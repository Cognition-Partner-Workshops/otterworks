from pathlib import Path
import re
import sys

import duckdb
import pytest

from parity import local_audit as audit
from parity.provenance import audit_branch, provenance
from parity.semantics import columns

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from audit_outputs import outputs
import assess


@pytest.fixture
def target():
    connection = duckdb.connect()
    connection.execute('CREATE SCHEMA AUDIT')
    audit.execute(connection, (audit.SQL / '00_tables.sql').read_text(), '20261109')
    yield connection
    connection.close()


@pytest.mark.parametrize('rows', [[], [(1, 2, 3, 4, '2026-11-09 01:02:03', 'DOC_EXPORT', None)],
                                [(1, 2, 3, 4, '2026-11-08 01:02:03', 'DOC_EXPORT', 'x')]])
def test_batch_load_and_shipped_summary(target, rows):
    if rows:
        target.executemany('INSERT INTO AUDIT.STG_AUDIT_EVENT VALUES (?,?,?,?,?,?,?)', rows)
    audit.execute(target, (audit.SQL / '10_load.sql').read_text(), '20261109')
    audit.execute(target, (audit.SQL / '35_reports.sql').read_text(), '20261109')
    assert target.execute('SELECT COUNT(*) FROM AUDIT.AUDIT_EVENT').fetchone()[0] == len(rows)
    expected = 1 if rows and rows[0][4].startswith('2026-11-09') else 0
    assert target.execute('SELECT COUNT(*) FROM AUDIT.AUDIT_DAILY_SUMMARY').fetchone()[0] == expected
    if expected:
        assert target.execute('SELECT SUMMARY_ID,EVENT_COUNT,EXPORT_COUNT FROM AUDIT.AUDIT_DAILY_SUMMARY').fetchall() == [(10000000004, 1, 0)]


def test_summary_explicit_delete_scope_and_recon_update(target):
    target.execute("INSERT INTO AUDIT.AUDIT_DAILY_SUMMARY VALUES (2,'2020-01-01',1,3,1),(10000000002,'2020-01-01',2,3,1)")
    audit.execute(target, (audit.SQL / '35_reports.sql').read_text(), '20261109')
    assert target.execute('SELECT SUMMARY_ID FROM AUDIT.AUDIT_DAILY_SUMMARY').fetchall() == [(2,)]
    target.execute("INSERT INTO AUDIT.AUDIT_RECON VALUES (1,'2026-11-09',0,8,3,99),(2,'2026-11-08',0,8,3,99)")
    audit.execute(target, (audit.SQL / '45_finish.sql').read_text(), '20261109')
    assert target.execute('SELECT DIFFERENCE_COUNT FROM AUDIT.AUDIT_RECON ORDER BY RECON_ID').fetchall() == [(5,), (99,)]


@pytest.mark.parametrize('empty', [False, True])
def test_landing_reads_headerless_files_and_missing_file_fails(target, tmp_path, empty):
    for table, feed in re.findall(r'COPY INTO __RUN_DATABASE__\.AUDIT\.(STG_\w+)\s+FROM @__RUN_DATABASE__\.AUDIT\.LANDING/audit/(\w+)/',
                                 (audit.SQL / '05_landing.sql').read_text()):
        path = tmp_path / 'audit' / feed
        path.mkdir(parents=True)
        definitions = target.execute('DESCRIBE AUDIT.' + table).fetchall()
        values = ['2026-11-09 01:02:03' if 'TIMESTAMP' in c[1] else '2026-11-09' if c[1] == 'DATE'
                  else 'x' if c[1] == 'VARCHAR' else '1' for c in definitions]
        (path / '20261109.psv').write_text('' if empty else '|'.join(values) + '\n')
    evidence = audit.landing(target, '20261109', tmp_path)
    assert len(evidence) == 9
    assert target.execute('SELECT COUNT(*) FROM AUDIT.STG_AUDIT_EVENT').fetchone() == (0 if empty else 1,)
    assert len(evidence['STG_AUDIT_EVENT']['sha256']) == 64
    with pytest.raises(FileNotFoundError):
        audit.landing(target, '20261108', tmp_path)


@pytest.mark.parametrize('text', ['CALL X.AUDIT.UNKNOWN()', 'CALL X.AUDIT.P_DAILY_SUMMARY(42)',
                                'DROP TABLE AUDIT.AUDIT_EVENT', "SELECT TO_CHAR(CURRENT_DATE,'bad')"])
def test_unsupported_execution_is_not_silently_skipped(target, text):
    with pytest.raises(ValueError):
        audit.execute(target, text, '20261109')


def test_invalid_date_and_missing_input_fail_closed(target):
    with pytest.raises(ValueError):
        audit.execute(target, 'SELECT 1', "20261109');DROP TABLE X")
    with pytest.raises(duckdb.Error):
        audit.execute(target, (audit.SQL / '40_reconciliation.sql').read_text(), '20261109')


@pytest.fixture
def pc(target):
    target.execute('CREATE SCHEMA AUDIT_PC')
    for table in audit.PC_TABLES:
        target.execute('CREATE TABLE AUDIT_PC.' + table + ' AS SELECT * FROM AUDIT.' + table + ' WHERE FALSE')
    target.execute('CREATE SEQUENCE AUDIT_PC.SUMMARY_SEQ START 50001')
    return target


def test_converted_powercenter_workflow_empty(pc):
    audit.execute(pc, 'CALL X.AUDIT_PC.WF_SFX_AUDIT_DAILY()', '20261109')
    assert all(pc.execute('SELECT COUNT(*) FROM AUDIT_PC.' + table).fetchone() == (0,) for table in audit.PC_TABLES)


def test_converted_powercenter_transformations_and_routing(pc):
    pc.execute("INSERT INTO AUDIT.STG_AUDIT_EVENT VALUES (1,2,0,-1,'2026-11-09 01:02:03',' doc_export ','')")
    pc.execute("INSERT INTO AUDIT.STG_SECURITY_ALERT VALUES (1,2,3,'2026-11-09','high','open'),(2,2,3,'2026-11-09','low','open'),(3,2,3,'2026-11-09','unknown','open')")
    audit.execute(pc, 'CALL X.AUDIT_PC.WF_SFX_AUDIT_DAILY()', '20261109')
    assert pc.execute('SELECT DOCUMENT_ID,CUSTOMER_ID,EVENT_TYPE,DETAILS FROM AUDIT_PC.AUDIT_EVENT').fetchall() == [(None,None,'DOC_EXPORT','DOC_EXPORT by user 2')]
    assert pc.execute('SELECT SUMMARY_ID,EVENT_COUNT,EXPORT_COUNT FROM AUDIT_PC.AUDIT_DAILY_SUMMARY').fetchall() == [(50001,1,1)]
    assert pc.execute('SELECT ALERT_ID,STATUS_CD FROM AUDIT_PC.SECURITY_ALERT ORDER BY ALERT_ID').fetchall() == [(1,'ESCALATED'),(2,'OPEN')]
    audit.execute(pc, 'CALL X.AUDIT_PC.S_M_SFX_SECURITY_ALERT()', '20261109')
    assert pc.execute('SELECT COUNT(*) FROM AUDIT_PC.SECURITY_ALERT').fetchone() == (2,)
    pc.execute("UPDATE AUDIT_PC.STG_AUDIT_EVENT SET DETAILS='changed'")
    audit.execute(pc, 'CALL X.AUDIT_PC.S_M_SFX_AUDIT_EVENT()', '20261109')
    assert pc.execute('SELECT EVENT_ID,DETAILS FROM AUDIT_PC.AUDIT_EVENT').fetchall() == [(1,'changed')]


@pytest.mark.parametrize('populated', [False, True])
def test_shipped_macro_resultset(target, populated):
    if populated:
        target.execute("INSERT INTO AUDIT.AUDIT_RECON VALUES (1,'2026-11-09',0,5,2,3),(2,'2026-11-08',0,5,2,3)")
    audit.execute(target, "CALL X.AUDIT.M_RECON_TOTALS('20261109')", '20261109')
    assert target.fetchall() == ([(1,5,2,3)] if populated else [])


def test_generic_reconcile_write_precedes_bteq_counts(target):
    text = (audit.SQL / '40_reconciliation.sql').read_text()
    for schema in ('USERS','DOCUMENTS','BILLING'):
        target.execute('CREATE SCHEMA ' + schema)
    inputs = set(re.findall(r'FROM __RUN_DATABASE__\.((?:USERS|DOCUMENTS|BILLING)\.\w+)', text))
    for name in inputs:
        target.execute('CREATE TABLE ' + name + ' (ID INTEGER)')
    target.execute('INSERT INTO DOCUMENTS.STG_STORAGE_USAGE_DAILY VALUES (1),(2)')
    target.execute('INSERT INTO DOCUMENTS.STORAGE_USAGE_DAILY VALUES (1)')
    audit.execute(target, text, '20261109')
    audit.execute(target, (audit.SQL / '45_finish.sql').read_text(), '20261109')
    assert target.execute('SELECT SOURCE_COUNT,TARGET_COUNT,DIFFERENCE_COUNT FROM AUDIT.AUDIT_RECON WHERE RECON_ID=21000000001').fetchall() == [(2,1,1)]
    assert target.execute('SELECT COUNT(*) FROM AUDIT.AUDIT_RECON').fetchone() == (38,)


def test_mapping_outputs_are_not_batch_outputs_and_retire_spark_unchanged():
    objects = assess.build()['objects']
    audit_objects = [obj for obj in objects if obj['subject_area'] == 'audit']
    assert len(audit_objects) == 57
    for obj in audit_objects:
        assert obj['status'] == 'not_started'
        if obj['target_type'] == 'retire' or obj['system'] == 'spark':
            assert outputs(obj) == obj['output_relations']
            continue
        assert obj['output_relations']
        if obj['system'] == 'powercenter':
            assert all(name.startswith('SFX_AUDIT_PC.') for name in obj['output_relations'])
        evidence = provenance(obj)
        assert any(evidence['converted'].values()), obj['name']
        assert all('/' + audit_branch() + '/' in item['url'] for item in evidence['source'])
    billing = next(obj for obj in objects if obj['name'] == 'SFX_BILLING.CUSTOMER_ACCOUNT')
    assert '/devin/sfx1119-billing-parity/' in provenance(billing)['source'][0]['url']
    assert columns('SFX_AUDIT_PC.AUDIT_EVENT') == columns('SFX_AUDIT.AUDIT_EVENT')


def test_audit_error_does_not_clear_billing_evidence(target):
    before = duckdb.connect()
    ready = {'BILLING.T'}
    errors, evidence = audit.materialize(before, target, {'SFX_AUDIT.AUDIT_EVENT'}, '', ready)
    assert 'BILLING.T' in ready
    assert 'AUDIT.AUDIT_EVENT' in errors
    before.close()
