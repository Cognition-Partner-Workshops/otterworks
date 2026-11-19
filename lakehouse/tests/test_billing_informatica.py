import json
import os
import shutil
import uuid
import zlib
from datetime import date
from decimal import Decimal

import pytest

from lakehouse.billing import informatica as I
from lakehouse.billing import informatica_reference as reference
from lakehouse.billing.informatica_control import control
from lakehouse.orchestration.graph import load
from lakehouse.parity.readers import postgres_connection
from lakehouse.runtime.layout import data_root


def row(table, **values):
    return dict.fromkeys(I.columns(table)) | values


def raw(table, **values):
    return {k.upper(): None if v is None else str(v) for k, v in row(table, **values).items()}


def test_informatica_empty_normal_errors_and_writers(tmp_path):
    for table in I.ORDER:
        result, rejects, errors, end = I.mapping(table, [], [])
        assert not result and not rejects and not errors
    data = [raw('CUSTOMER_ACCOUNT', customer_id='123abc', account_name='  Name  ', status_cd=' active ',
                currency_cd=None, created_dt='2026-11-09', account_number=' abc '),
            raw('CUSTOMER_ACCOUNT', customer_id='bad')]
    staged, rejected, errors, _ = I.mapping('STG_CUSTOMER_ACCOUNT', [], data)
    assert staged[0]['customer_id'] == 123 and staged[0]['currency_cd'] == 'USD'
    assert staged[0]['account_name'] == 'Name' and staged[0]['account_number'] == 'ABC'
    assert len(errors) == 1 and not rejected
    accounts, rejects, _, _ = I.mapping('CUSTOMER_ACCOUNT', [], staged + staged)
    assert len(accounts) == 1 and len(rejects) == 1
    updated, rejects, _, _ = I.mapping('CUSTOMER_ACCOUNT', accounts, [staged[0] | {'account_name': 'New'}])
    assert updated[0]['account_name'] == 'New' and not rejects
    _, rejects, _, _ = I.mapping('INVOICE_HDR', [], [row('INVOICE_HDR', invoice_id=1, customer_id=999)])
    assert rejects[0]['record'].startswith('3,D,1,')
    lines, rejects, errors, _ = I.mapping('INVOICE_LINE', [], [raw('INVOICE_LINE', invoice_line_id=1,
        invoice_id=1, quantity=3, unit_price='1.235'), raw('INVOICE_LINE', invoice_line_id=None)])
    assert lines[0]['line_amount'] == Decimal('3.72') and not rejects and not errors
    with pytest.raises(ValueError, match='null primary'):
        I.shape(row('PAYMENT'), 'PAYMENT')
    with pytest.raises(ValueError, match='out of range'):
        I.shape(row('PAYMENT', payment_id=2**63), 'PAYMENT')
    I.output(tmp_path, 'STG_CUSTOMER_ACCOUNT', staged, [], errors)
    assert (tmp_path / 'stg_customer_account.psv').is_file()


def test_informatica_journal_filters_tax_sequence_and_retention():
    D = Decimal
    source = [row('INVOICE_HDR', invoice_id=1, total_amount=D('10.00'), tax_amount=None,
                  invoice_dt=date(2026, 11, 9), currency_cd='usd', invoice_number='A'),
              row('INVOICE_HDR', invoice_id=2, total_amount=D('10.00'), tax_amount=D('0.00')),
              row('INVOICE_HDR', invoice_id=3, total_amount=D('0.00'), tax_amount=None)]
    prior = [row('GL_JOURNAL_LINE', journal_line_id=1, invoice_id=1),
             row('GL_JOURNAL_LINE', journal_line_id=2, invoice_id=1, credit_note_id=1),
             row('GL_JOURNAL_LINE', journal_line_id=3, invoice_id=3)]
    gl = [{'account_number': n, 'gl_account_id': i} for i, n in [(1, '1200'), (2, '2300'), (3, '2200')]]
    rows, rejects, errors, end = I.mapping('GL_JOURNAL_LINE', prior, source, gl_accounts=gl, sequence=100)
    assert len(rows) == 7 and not errors and not rejects and end == 105
    new = rows[2:]
    assert sum(r['debit_amount'] for r in new) == sum(r['credit_amount'] for r in new)
    assert [r['journal_line_id'] for r in new] == list(range(100, 105))
    assert new[-1]['credit_amount'] == D('0.76')
    rows, _, errors, _ = I.mapping('GL_JOURNAL_LINE', prior, source, tax_rate='-1')
    assert len(errors) == 2
    with pytest.raises(OverflowError, match='Sequence'):
        I.mapping('GL_JOURNAL_LINE', [], source, sequence=2**63)


def test_informatica_decision_alert_and_scheduler(tmp_path, monkeypatch):
    assert control(tmp_path, '20261109', 'start') == 0
    sessions = {t: {'Status': 'SUCCEEDED', 'TgtFailedRows': 0} for t in I.ORDER}
    I.save(tmp_path / 'sessions.json', sessions)
    assert control(tmp_path, '20261109', 'worklet') == 0
    assert control(tmp_path, '20261109', 'decision') == 0
    assert control(tmp_path, '20261109', 'alert') == 0
    assert not (tmp_path / 'outbox/gl_posting_alert.json').exists()
    assert control(tmp_path, '20261109', 'payment') == 0
    assert control(tmp_path, '20261109', 'finish') == 0
    for state in ({'Status': 'FAILED', 'TgtFailedRows': 0}, {'Status': 'SUCCEEDED', 'TgtFailedRows': 1}):
        sessions['GL_JOURNAL_LINE'] = state
        sessions['PAYMENT']['Status'] = 'NOTSTARTED'
        I.save(tmp_path / 'sessions.json', sessions)
        control(tmp_path, '20261109', 'decision')
        assert control(tmp_path, '20261109', 'payment') == 0
        monkeypatch.delenv('SFX_LH_SMTP_HOST', raising=False)
        assert control(tmp_path, '20261109', 'alert') == 1
        assert json.loads((tmp_path / 'outbox/gl_posting_alert.json').read_text())['status'] == 'QUEUED'
    sent = []

    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ('localhost', 25, 30)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def send_message(self, message):
            sent.append(message)

    monkeypatch.setenv('SFX_LH_SMTP_HOST', 'localhost')
    monkeypatch.setattr('lakehouse.billing.informatica_control.smtplib.SMTP', SMTP)
    assert control(tmp_path, '20261109', 'alert') == 1 and len(sent) == 1
    assert sent[0]['To'] == 'finance-data-oncall@otterworks.example'
    with pytest.raises(ValueError):
        control(tmp_path, '20260230', 'start')
    dag = load()['lakehouse_daily']
    nodes = {n['id']: n for n in dag['nodes']}
    assert dag['schedule'] == '@daily' and dag['timezone'] == 'UTC'
    assert nodes['infa_billing_start']['depends_on'] == ['dbt_billing_reporting']
    assert nodes['infa_billing_worklet']['depends_on'] == ['infa_billing_customer_account', 'infa_billing_stg_invoice_hdr']
    assert nodes['infa_billing_decision']['depends_on'] == ['infa_billing_gl_journal_line']
    assert nodes['infa_billing_payment']['depends_on'] == ['infa_billing_decision']
    assert nodes['infa_billing_alert']['kind'] == 'export'
    assert '--action' in nodes['infa_billing_alert']['command']


@pytest.mark.skipif(os.environ.get('SFX_LH_INFA_NATIVE_TEST') != '1', reason='requires the legacy emulator')
def test_informatica_native_reject_row_parity(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'test-infa-' + uuid.uuid4().hex)
    monkeypatch.setenv('TD_PG_PORT', str(54500 + zlib.crc32(os.environ.get('LEGACY_NS', 'sfx-d1110-before').encode()) % 1000))
    monkeypatch.setattr(reference, 'data_root', lambda: tmp_path)
    day = '20261109'
    root = tmp_path / 'informatica' / day
    I.save(root / 'inputs.json', {'sequence_start': 1000000000001})
    samples = {
        'CUSTOMER_ACCOUNT': [raw('CUSTOMER_ACCOUNT', customer_id=900001, account_name=' Name ', status_cd=' active ',
                                 created_dt='2026-11-09', account_number=' abc '),
                             raw('CUSTOMER_ACCOUNT', customer_id=900001, account_name='Duplicate'),
                             raw('CUSTOMER_ACCOUNT', account_name='Null ID'), raw('CUSTOMER_ACCOUNT', customer_id='bad')],
        'INVOICE_HDR': [raw('INVOICE_HDR', invoice_id=900001, customer_id=900001, total_amount='10.00', invoice_dt='2026-11-09'),
                        raw('INVOICE_HDR', invoice_id=900002, customer_id=999999, total_amount='20.00', invoice_dt='2026-11-09'),
                        raw('INVOICE_HDR', invoice_id=900003, customer_id=900001, invoice_dt='2026-11-09'),
                        raw('INVOICE_HDR', invoice_id=900004, customer_id=900001, total_amount='0.00', invoice_dt='2026-11-09'),
                        raw('INVOICE_HDR', invoice_id=900005, invoice_dt='invalid')],
        'INVOICE_LINE': [raw('INVOICE_LINE', invoice_line_id=900001, invoice_id=900001, quantity=3, unit_price='1.235'),
                         raw('INVOICE_LINE', invoice_line_id=900001, invoice_id=900001, description=' updated ', line_amount='1'),
                         raw('INVOICE_LINE'), raw('INVOICE_LINE', invoice_line_id='bad')],
        'PAYMENT': [raw('PAYMENT', payment_id=900001, amount='2.345', method_cd=' bank '),
                    raw('PAYMENT', payment_id=900001, amount='3'), raw('PAYMENT', payment_id=900002), raw('PAYMENT', payment_id='bad')],
    }
    landing = tmp_path / 'landing'
    for table, rows in samples.items():
        I.records(landing / 'billing' / table / (day + '.psv'), rows, [c.upper() for c in I.columns(table)])
    with postgres_connection() as connection:
        state = {}
        for table in I.BASE:
            cursor = connection.execute('SELECT * FROM sfx_billing.' + table.lower())
            names = [c.name for c in cursor.description]
            state[table] = [{k: v.rstrip(' ') if isinstance(v, str) and any(
                c.name.lower() == k and c.kind.startswith('C') for c in I.METADATA[table.removeprefix('STG_')].columns)
                and not table.startswith('STG_') else v for k, v in zip(names, row)} for row in cursor.fetchall()]
    I.save(root / 'inputs/prior.json', state)
    sequence = 1000000000001
    modern = tmp_path / 'modern'
    for table in I.ORDER:
        source = state['STG_CUSTOMER_ACCOUNT'] if table == 'CUSTOMER_ACCOUNT' else state['STG_INVOICE_HDR'] if table in (
            'INVOICE_HDR', 'GL_JOURNAL_LINE') else I.flat_rows(landing, table.removeprefix('STG_'), day)
        values, rejects, errors, sequence = I.mapping(table, state[table], source, state['CUSTOMER_ACCOUNT'],
                                                     state['GL_ACCOUNT'], sequence=sequence)
        state[table] = values
        I.output(modern, table, values, rejects, errors)
    reference.prepare(landing, day)
    for path in modern.glob('*.psv'):
        assert path.read_bytes() == (root / 'reference' / path.name).read_bytes(), path.name
    assert (modern / 'customer_account_rejects.psv').stat().st_size > 0
    assert (modern / 'invoice_hdr_rejects.psv').stat().st_size > 0
    assert (modern / 'payment_transformation_rejects.psv').stat().st_size > 0
    shutil.rmtree(data_root())
