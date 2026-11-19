from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from sqlglot import exp

from parity import local_billing, provenance, semantics
from parity.ladder import local_compare

ROOT = Path(__file__).resolve().parents[3]
BILLING = ROOT / 'migration/dw-exit/billing'


def test_source_char_rules_and_view_lineage():
    assert semantics.char_columns('CUSTOMER_ACCOUNT') == ['COUNTRY_CD','CURRENCY_CD','STATUS_CD']
    assert 'PLAN_CODE' in semantics.char_columns('V_SUBSCRIPTION_PLANS')
    assert 'INVOICE_PERIOD' in semantics.char_columns('V_INVOICE_REVENUE')
    assert 'PLAN_CODE' not in semantics.char_columns('SUBSCRIPTION')
    assert semantics.char_columns('STG_CUSTOMER_ACCOUNT') == []
    assert semantics.char_columns('UNKNOWN') == []


@pytest.mark.parametrize('values,expected', [([], 'DECIMAL(38,0)'), ([Decimal('7809.79')], 'DECIMAL(38,2)'), ([None,Decimal('0.00001')], 'DECIMAL(38,5)')])
def test_unconstrained_numeric_scale(values,expected):
    assert semantics.numeric_type(values,None,None) == expected


def test_numeric_scale_fails_closed():
    with pytest.raises(ValueError):
        semantics.numeric_type([Decimal('1e-39')],None,None)


@pytest.mark.parametrize('before,after,passed', [('ACTIVE   ','ACTIVE',True), ('Active','ACTIVE',False), (None,None,True)])
def test_char_padding_only(before,after,passed):
    with duckdb.connect() as b, duckdb.connect() as a:
        b.execute('CREATE SCHEMA SFX_BILLING'); a.execute('CREATE SCHEMA BILLING')
        for c,s,v in [(b,'SFX_BILLING',before),(a,'BILLING',after)]:
            c.execute(f'CREATE TABLE {s}.CUSTOMER_ACCOUNT (ID INTEGER, STATUS_CD VARCHAR, ACCOUNT_NAME VARCHAR)')
            c.execute(f'INSERT INTO {s}.CUSTOMER_ACCOUNT VALUES (1, ?, ?)',[v,'Name'])
        result=local_compare(b,a,'SFX_BILLING.CUSTOMER_ACCOUNT','BILLING.CUSTOMER_ACCOUNT')
        assert result['passed'] == passed
        assert 'STATUS_CD' in result['comparison_rules']['trailing_pad_insensitive']
        a.execute("UPDATE BILLING.CUSTOMER_ACCOUNT SET ACCOUNT_NAME='Name '")
        assert not local_compare(b,a,'SFX_BILLING.CUSTOMER_ACCOUNT','BILLING.CUSTOMER_ACCOUNT')['passed']


def test_subscription_view_case_and_padding():
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA BILLING')
        c.execute('CREATE TABLE BILLING.SUBSCRIPTION (SUBSCRIPTION_ID BIGINT,CUSTOMER_ID BIGINT,PLAN_CODE VARCHAR)')
        c.execute('CREATE TABLE BILLING.PLAN_CATALOG (PLAN_CODE VARCHAR,MONTHLY_FEE DECIMAL(10,2))')
        c.execute("INSERT INTO BILLING.SUBSCRIPTION VALUES (1,1,'Pro '),(2,2,'absent')")
        c.execute("INSERT INTO BILLING.PLAN_CATALOG VALUES ('PRO',19.50)")
        statement=next(s for s in local_billing.statements(BILLING/'30_views.sql','20261109') if 'V_SUBSCRIPTION_PLANS' in s.this.sql())
        c.execute(statement.sql(dialect='duckdb'))
        assert c.execute('SELECT * FROM BILLING.V_SUBSCRIPTION_PLANS').fetchall()==[(1,1,'PRO',Decimal('19.50'))]
        c.execute('DELETE FROM BILLING.SUBSCRIPTION')
        assert c.execute('SELECT * FROM BILLING.V_SUBSCRIPTION_PLANS').fetchall()==[]


def test_shipped_chain_extraction_and_empty_execution():
    assert local_billing.STAGES == ('10_load.sql','15_storage.sql','20_routines.sql','30_views.sql','40_close.sql')
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA BILLING')
        for statement in local_billing.statements(BILLING/'00_tables.sql','20261109'):
            for col in statement.find_all(exp.ColumnDef):
                col.set('constraints',[])
            c.execute(statement.sql(dialect='duckdb'))
        c.execute('CREATE TABLE BILLING.STORAGE_USAGE_INPUT (CUSTOMER_ID BIGINT,BYTES_USED BIGINT,USAGE_DT DATE)')
        errors=local_billing.execute(c,BILLING,set(),'20261109')
        assert errors == {}
        assert c.execute('SELECT COUNT(*) FROM BILLING.INVOICE_LINE').fetchone()==(0,)


def test_stage_failure_is_closed(tmp_path):
    (tmp_path/'10_load.sql').write_text('SELECT 1;')
    with duckdb.connect() as c:
        ready={'BILLING.T'}
        errors=local_billing.execute(c,tmp_path,ready,'20261109')
        assert 'Unsupported local billing statement' in errors['*']
        assert ready == set()


def test_missing_stage_fails_closed(tmp_path):
    with duckdb.connect() as c:
        ready={'BILLING.T'}
        assert 'FileNotFoundError' in local_billing.execute(c,tmp_path,ready,'20261109')['*']
        assert not ready


def test_date_format_transpilation_and_procedure_wrapper_fail(tmp_path):
    path=tmp_path/'40_close.sql'
    path.write_text("UPDATE BILLING.T SET DAY=TO_DATE('09/11/2026','DD/MM/YYYY');")
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA BILLING')
        c.execute('CREATE TABLE BILLING.T (DAY DATE)')
        c.execute("INSERT INTO BILLING.T VALUES (NULL)")
        for statement in local_billing.statements(path,'20261109'):
            c.execute(statement.sql(dialect='duckdb'))
        assert str(c.execute('SELECT DAY FROM BILLING.T').fetchone()[0]) == '2026-11-09'
    with pytest.raises(ValueError,match='Business date'):
        list(local_billing.statements(path,'invalid'))
    path=tmp_path/'20_routines.sql'
    path.write_text('')
    with pytest.raises(ValueError,match='Expected one'):
        list(local_billing.statements(path,'20261109'))


def test_provenance_ranges_are_real_and_clickable():
    obj={'name':'SFX_BILLING.INVOICE_HDR','kind':'table','source':'warehouse/teradata/ddl/billing/00_tables.sql','output_relations':['SFX_BILLING.INVOICE_HDR']}
    p=provenance.provenance(obj)
    assert {Path(x['file']).name for x in p['converted']['SFX_BILLING.INVOICE_HDR']} >= {'10_load.sql','20_routines.sql','40_close.sql'}
    for entry in p['source']+p['converted']['SFX_BILLING.INVOICE_HDR']+list(p['metrics'].values()):
        lines=(ROOT/entry['file']).read_text().splitlines()
        assert 1 <= entry['start_line'] <= entry['end_line'] <= len(lines)
        assert '/blob/devin/sfx1119-billing-parity/' in entry['url']
        assert entry['url'].endswith(f"#L{entry['start_line']}-L{entry['end_line']}")
    assert provenance.provenance(dict(obj,output_relations=[]))['conversion_note']


@pytest.mark.parametrize('name,kind,system,source', [
    ('SFX_BILLING.M_CURRENCY_TOTALS','macro','teradata','warehouse/teradata/macros/currency_totals.sql'),
    ('12_invoice_monthly','bteq','teradata','warehouse/teradata/scripts/billing/12_invoice_monthly.bteq'),
    ('billing_churn_score','spark_job','spark','etl/spark/jobs/py/billing_churn_score.py'),
])
def test_unmeasured_provenance_links_candidates_without_claiming_measurement(name,kind,system,source):
    p=provenance.provenance(dict(name=name,kind=kind,system=system,source=source))
    assert p['source']
    assert any(p['converted'].values())
    assert 'not measured' in p['conversion_note']
