import hashlib
import json
import os
import random
import subprocess
import time
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

import custbill as cb

LEGACY = Path(__file__).resolve().parents[1] / 'legacy-extra'
SPECIAL_AMOUNTS = ('inf', 'Inf', 'nan', 'infinity', ' +Inf', ' -Inf',
                   ' +nan', ' -nan', ' +infinity', ' -INFINITY', '1e400', '-1e400')
SIGNED_INFINITY = ('+inf', '-inf', '+Inf', '-INF', '+infinity', '-infinity')
FIXED_AMOUNTS = tuple(zip(SPECIAL_AMOUNTS,
                          ('0.00', '0.00', '0.00', '0.00', '+inf', '-inf',
                           '+nan', '-nan', '+inf', '-inf', '+inf', '-inf'), strict=True))
FIXED_AMOUNTS += tuple((char + '123', '1.23') for char in ' \t\r\v\f')
FIXED_AMOUNTS += tuple(zip(SIGNED_INFINITY,
                           ('+inf', '-inf', '+inf', '-inf', '+inf', '-inf'), strict=True))


@pytest.fixture(scope='session')
def spark():
    os.environ['SPARK_LOCAL_IP'] = '127.0.0.1'
    session = SparkSession.builder.master('local[*]').appName('ow_tp_custbill_tests').getOrCreate()
    session.sparkContext.addPyFile(str(Path(cb.__file__).resolve()))
    yield session
    session.stop()


def record(amount='000000001234'):
    return ('C000000001' + 'CUSTOMER'.ljust(30) + '20250101' + amount + 'USD01').encode()


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for directory in ('incoming', 'parsed', 'reports', 'archive')
            for p in (root / directory).glob('*') if p.is_file()}


def test_real_awk_pipeline(tmp_path):
    randomizer = random.Random(2542)
    bodies = [b'', b'a', b'x' * 80, b'\r', record(), record(b'12bad'.decode().ljust(12)),
              record('-00000000050'),
              record()[:5] + b'|' + record()[6:],
              record().replace(b'CUSTOMER', b'\xffUSTOME\x00'), record() + b'\r']
    bodies += [bytes(randomizer.choice([32, 65, 124, 13, 255, 49]) for _ in range(randomizer.randrange(90)))
               for _ in range(100)]
    def portable_amount(row):
        fields = b'|'.join(row[a:b] for a, b in
                           ((0, 10), (10, 40), (40, 48), (48, 60), (60, 63), (63, 65))).split(b'|')
        return not fields[3].startswith((b' ', b'\t', b'\r', b'\v', b'\f'))
    bodies = [row for row in bodies if portable_amount(row)]
    data = b'HDR header\n' + b'\n'.join(bodies) + b'\nTRL0000000110'
    path = tmp_path / 'input'
    path.write_bytes(data)
    command = r'''paste -d'|' <(cut -c1-10 "$1") <(cut -c11-40 "$1") <(cut -c41-48 "$1") <(cut -c49-60 "$1") <(cut -c61-63 "$1") <(cut -c64-65 "$1") | awk -F'|' 'BEGIN{OFS="|"} {gsub(/ +$/,"",$1); gsub(/ +$/,"",$2); gsub(/ +$/,"",$5); $4=sprintf("%.2f",($4+0)/100); $3=substr($3,1,4)"-"substr($3,5,2)"-"substr($3,7,2); print}' '''
    stripped = subprocess.check_output(['sed', '-e', '/^HDR/d', '-e', '/^TRL/d', str(path)])
    path.write_bytes(stripped)
    expected = subprocess.check_output(['bash', '-c', command, '_', str(path)], env=dict(os.environ, LC_ALL='C'))
    assert cb.parse_bytes(data) == expected
    assert cb.parse_bytes(b'') == b''
    assert cb.parse_bytes(b'x') == cb.parse_bytes(b'x\n')


def test_fixed_dialect_amounts(monkeypatch):
    monkeypatch.setenv('PATH', '/no-executables')
    for amount, expected in FIXED_AMOUNTS:
        assert cb.parse_bytes(record(amount.ljust(12))) == (
            f'C000000001|CUSTOMER|2025-01-01|{expected}|USD|01\n'.encode())


def test_dialect_amounts_ledger(spark, tmp_path, monkeypatch):
    data = (b'HDR\n' + b'\n'.join(record(amount.ljust(12)) for amount, _ in FIXED_AMOUNTS)
            + f'\nTRL{len(FIXED_AMOUNTS):010d}\n'.encode())
    for name, strict in (('CUSTBILL_COMPAT', '0'), ('CUSTBILL_STRICT', '1')):
        source = tmp_path / 'incoming' / (name + '.dat')
        cb.atomic(source, data)
        monkeypatch.setenv('CUSTBILL_STRICT', strict)
        if strict == '1':
            with pytest.raises(ValueError, match='validation failed'):
                cb.parse(spark, tmp_path)
            assert source.exists()
            assert not (tmp_path / 'parsed' / (name + '.psv')).exists()
        else:
            cb.parse(spark, tmp_path)
            assert not source.exists()
        ledger = json.loads(next((tmp_path / 'ledger').glob(name + '*.json')).read_text())
        assert ledger['errors'] == [
            {'row': index + 1, 'reason': 'invalid schema/date/attribution'}
            for index in range(len(FIXED_AMOUNTS))]
        assert next((tmp_path / 'quarantine').glob(name + '*')).read_bytes() == data


def test_real_perl_order_and_empty(spark, tmp_path):
    parsed = tmp_path / 'parsed'
    parsed.mkdir()
    randomizer = random.Random(25)
    for name in ('CUSTBILL_Z.psv', 'CUSTBILL_A.psv'):
        amounts = ['1e16', '1', '-1e16'] + [str(randomizer.uniform(-1e10, 1e10)) for _ in range(300)]
        rows = [f'C|N|D|{amount}|USD|01\n'.encode() for amount in amounts]
        rows += [f'C|N|D|{amount}|N{index:02d}|01\n'.encode()
                 for index, amount in enumerate(SPECIAL_AMOUNTS)]
        rows += [b'C|N|D|12garbage|EUR|99\r\n', b'|skip|D|999|USD|01\n', b'C|N|D||GBP|\n', b'C|N|D|-.5|USD|02']
        (parsed / name).write_bytes(b''.join(rows))
    env = dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(tmp_path), LC_ALL='C', TZ='UTC')
    subprocess.run(['perl', str(LEGACY / 'jobs/finance_excel_report.pl')], env=env, check=True, capture_output=True)
    expected = next((tmp_path / 'reports').glob('*.csv')).read_bytes()
    cb.report(spark, tmp_path)
    assert next((tmp_path / 'reports').glob('*.csv')).read_bytes() == expected
    assert next((tmp_path / 'reports').glob('*.xls')).read_bytes() == expected
    assert next((tmp_path / 'delivery').glob('*.xls')).read_bytes() == expected
    for path in parsed.glob('*'):
        path.unlink()
    cb.report(spark, tmp_path)
    assert next((tmp_path / 'reports').glob('*.csv')).read_bytes() == b'Currency,RecordType,RecordCount,TotalAmount\n'


def test_signed_infinity_real_tools(tmp_path):
    data = (b'HDR\n' + b'\n'.join(record(amount.ljust(12)) for amount in SIGNED_INFINITY)
            + b'\nTRL0000000006\n')
    cb.atomic(tmp_path / 'incoming/CUSTBILL_SIGNED.dat', data)
    env = dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(tmp_path), LC_ALL='C', TZ='UTC')
    subprocess.run(['bash', str(LEGACY / 'jobs/parse_custbill_fixedwidth.sh')],
                   env=env, check=True, capture_output=True)
    actual = (tmp_path / 'parsed/CUSTBILL_SIGNED.psv').read_bytes()
    print('\nDefault awk legacy parse:\n' + actual.decode(), end='')
    print('Spark parse_bytes:\n' + cb.parse_bytes(data).decode(), end='')
    assert actual == cb.parse_bytes(data)
    errors = cb.validate(data)
    assert errors == [{'row': index + 1, 'reason': 'invalid schema/date/attribution'}
                      for index in range(len(SIGNED_INFINITY))]
    print('Parse validation errors:', errors)
    groups = [(f'S{index}', [amount]) for index, amount in enumerate(SIGNED_INFINITY)]
    groups += [('MIX', ['+inf', '-inf']), ('FINITE', ['+inf', '12.5'])]
    rows = b''.join(f'C|N|D|{amount}|{key}|01\n'.encode()
                    for key, amounts in groups for amount in amounts)
    (tmp_path / 'parsed/CUSTBILL_SIGNED.psv').write_bytes(rows)
    subprocess.run(['perl', str(LEGACY / 'jobs/finance_excel_report.pl')],
                   env=env, check=True, capture_output=True)
    expected = next((tmp_path / 'reports').glob('*.csv')).read_bytes()
    actual = cb.report_bytes(cb.report_inputs(('CUSTBILL_SIGNED.psv', rows)))
    print('Legacy Perl report:\n' + expected.decode(), end='')
    print('Spark report_bytes:\n' + actual.decode(), end='')
    assert actual == expected
    assert b'MIX,INVOICE,2,NaN\n' in actual
    assert b'FINITE,INVOICE,2,Inf\n' in actual


def test_chain_rerun_and_validation(spark, tmp_path, monkeypatch):
    drop = tmp_path / 'sftp-drop/upload'
    drop.mkdir(parents=True)
    data = b'HDR\n' + record() + b'\nTRL0000000099\n'
    (drop / 'CUSTBILL_TEST.dat').write_bytes(data)
    monkeypatch.setenv('CUSTBILL_DISTRIBUTION', '["ow_tp_finance_fixture"]')
    with cb.locked(tmp_path):
        cb.ingest(spark, tmp_path)
        cb.parse(spark, tmp_path)
        cb.report(spark, tmp_path)
    first = snapshot(tmp_path)
    with cb.locked(tmp_path):
        cb.ingest(spark, tmp_path)
        cb.parse(spark, tmp_path)
        cb.report(spark, tmp_path)
    assert snapshot(tmp_path) == first
    assert not list(drop.iterdir())
    assert (tmp_path / 'incoming/CUSTBILL_TEST.dat.done').read_bytes() == data
    ledger = next((tmp_path / 'ledger').glob('CUSTBILL*.json'))
    assert json.loads(ledger.read_text())['errors'][0]['reason'] == 'trailer mismatch'
    assert list((tmp_path / 'quarantine').iterdir())
    assert json.loads((tmp_path / 'ledger/delivery.json').read_text())['distribution'] == ['ow_tp_finance_fixture']
    # Replay the same completed transfer, not merely an empty drop.
    (drop / 'CUSTBILL_TEST.dat').write_bytes(data)
    cb.ingest(spark, tmp_path)
    cb.parse(spark, tmp_path)
    cb.report(spark, tmp_path)
    assert snapshot(tmp_path) == first


def test_errors_and_strict_mode(spark, tmp_path, monkeypatch):
    drop = tmp_path / 'sftp-drop/upload'
    drop.mkdir(parents=True)
    path = drop / 'CUSTBILL_BAD.dat'
    path.write_bytes(record())
    with pytest.raises(ValueError, match='incomplete transfer'):
        cb.ingest(spark, tmp_path)
    assert path.exists()
    path.write_bytes(b'HDR\nx\nTRL0000000001\n')
    cb.ingest(spark, tmp_path)
    monkeypatch.setenv('CUSTBILL_STRICT', '1')
    with pytest.raises(ValueError, match='validation failed'):
        cb.parse(spark, tmp_path)
    assert not list((tmp_path / 'parsed').glob('*'))
    assert (tmp_path / 'incoming/CUSTBILL_BAD.dat').exists()
    assert list((tmp_path / 'quarantine').iterdir())
    monkeypatch.setenv('CUSTBILL_DISTRIBUTION', 'not-json')
    with pytest.raises(json.JSONDecodeError):
        cb.report(spark, tmp_path)


def test_lock_process_and_release(tmp_path):
    script = 'import sys; from pathlib import Path; import custbill;\nwith custbill.locked(Path(sys.argv[1])): pass'
    command = [os.sys.executable, '-c', script, str(tmp_path)]
    with cb.locked(tmp_path):
        result = subprocess.run(command, check=False, capture_output=True)
        assert result.returncode != 0
        assert b'BlockingIOError' in result.stderr
    assert subprocess.run(command, check=False, capture_output=True).returncode == 0
    with pytest.raises(RuntimeError), cb.locked(tmp_path):
        raise RuntimeError('failed stage')
    assert subprocess.run(command, check=False, capture_output=True).returncode == 0


def test_retention_safe_rerun(tmp_path):
    raw = b'old'
    digest = hashlib.sha256(raw).hexdigest()
    cb.atomic(tmp_path / 'ledger/CUSTBILL_X.json', json.dumps({'file': 'CUSTBILL_X.dat', 'sha256': digest}).encode())
    archive = tmp_path / 'archive' / ('CUSTBILL_X.dat.' + digest)
    done = tmp_path / 'incoming/CUSTBILL_X.dat.done'
    cb.atomic(archive, raw)
    cb.atomic(done, b'newer run')
    old = time.time() - 3 * 86400
    os.utime(archive, (old, old))
    os.utime(done, (old, old))
    cb.retain(tmp_path, 1)
    cb.retain(tmp_path, 1)
    assert not archive.exists()
    assert done.read_bytes() == b'newer run'
    assert list((tmp_path / 'ledger').iterdir())
