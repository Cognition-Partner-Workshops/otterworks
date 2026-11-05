"""Local, byte-preserving CUSTBILL Spark stages."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from pyspark.sql import SparkSession

_AWK_FORMATS = {}


def lines(data):
    parts = data.decode('latin-1').split('\n')
    return parts[:-1] if parts[-1] == '' else parts


def number(value):
    """Convert a decimal numeric prefix for the fixed-width parser."""
    match = re.match(r'^[ \t\r\v\f]*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)', value)
    return float(match[1]) if match else 0.0


def perl_number(value):
    """Match Perl's case-insensitive Inf/NaN/infinity numeric conversion."""
    token = value.lstrip(' \t\r\v\f')
    match = re.match(r'^([+-]?)(inf(?:inity)?|nan)(?:$|[^A-Za-z])', token, re.IGNORECASE)
    if match:
        if match[2].lower() == 'nan':
            return math.nan
        return -math.inf if match[1] == '-' else math.inf
    match = re.match(r'^[ \t\r\v\f]*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)', value)
    return float(match[1]) if match else 0.0


def awk_formats(executable):
    """Probe host awk's non-finite coercion/printf dialect once per worker."""
    if executable in _AWK_FORMATS:
        return _AWK_FORMATS[executable]
    tokens = [sign + word for sign in ('', '+', '-') for word in ('inf', 'infinity', 'nan')]
    tokens += ['1e400', '-1e400']
    result = subprocess.run([executable, '{printf "%.2f\\n", ($0+0)/100}'],
                            input='\n'.join(tokens) + '\n', text=True, capture_output=True,
                            env=dict(os.environ, LC_ALL='C'), check=True)
    _AWK_FORMATS[executable] = dict(zip(tokens, result.stdout.splitlines(), strict=True))
    return _AWK_FORMATS[executable]


def awk_amount(value):
    """Render awk's special printf spellings after fixed-width numification."""
    special = re.match(r'^[ \t\r\v\f]*([+-]?(?:inf(?:inity)?|nan))(?:$|[^A-Za-z])', value, re.IGNORECASE)
    executable = os.environ.get('CUSTBILL_AWK', 'awk')
    if special:
        return awk_formats(executable)[special[1].lower()]
    amount = number(value) / 100
    if math.isinf(amount):
        return awk_formats(executable)['-1e400' if amount < 0 else '1e400']
    return f'{amount:.2f}'


def parse_bytes(data):
    result = []
    for line in lines(data):
        if line.startswith(('HDR', 'TRL')):
            continue
        fields = '|'.join(line[a:b] for a, b in
                          ((0, 10), (10, 40), (40, 48), (48, 60), (60, 63), (63, 65))).split('|')
        for index in (0, 1, 4):
            fields[index] = fields[index].rstrip(' ')
        fields[3] = awk_amount(fields[3])
        date = fields[2]
        fields[2] = date[:4] + '-' + date[4:6] + '-' + date[6:8]
        result.append('|'.join(fields) + '\n')
    return ''.join(result).encode('latin-1')


def validate(data):
    body = [s for s in lines(data) if not s.startswith(('HDR', 'TRL'))]
    trailers = [s[3:13] for s in lines(data) if s.startswith('TRL')]
    errors = []
    for index, row in enumerate(body):
        try:
            datetime.strptime(row[40:48], '%Y%m%d')
            valid = (len(row) == 65 and bool(row[:10].strip())
                     and row[48:60].isascii() and row[48:60].isdigit()
                     and row[60:63] in ('USD', 'EUR', 'GBP') and row[63:65] in ('01', '02')
                     and '|' not in row)
        except ValueError:
            valid = False
        if not valid:
            errors.append({'row': index + 1, 'reason': 'invalid schema/date/attribution'})
    if len(trailers) != 1 or not trailers[0].isdigit() or int(trailers[0]) != len(body):
        errors.append({'reason': 'trailer mismatch', 'actual': len(body), 'trailers': trailers})
    return errors


def parse_file(item):
    name, data = item
    return Path(name).name, parse_bytes(data), validate(data)


def report_inputs(item):
    name, data = item
    for index, line in enumerate(lines(data)):
        fields = line.split('|')
        while fields and fields[-1] == '':
            fields.pop()
        fields += [''] * max(0, 6 - len(fields))
        if fields[0]:
            yield Path(name).name, index, fields[4] + '|' + fields[5], perl_number(fields[3])


def report_bytes(rows):
    totals = {}
    for _, _, key, amount in sorted(rows):
        count, total = totals.get(key, (0, 0.0))
        totals[key] = count + 1, total + amount
    output = 'Currency,RecordType,RecordCount,TotalAmount\n'
    for key, (count, amount) in sorted(totals.items()):
        ccy, rt = key.split('|')[:2]
        label = {'01': 'INVOICE', '02': 'CREDIT'}.get(rt, f'UNKNOWN({rt})')
        if math.isnan(amount):
            rendered = 'NaN'
        elif math.isinf(amount):
            rendered = '-Inf' if amount < 0 else 'Inf'
        else:
            rendered = f'{amount:.2f}'
        output += f'{ccy},{label},{count},{rendered}\n'
    return output.encode('latin-1')


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.custbill-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.custbill.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def read_files(spark, paths):
    # binaryFiles preserves non-UTF8 bytes; one task per file, no text decoder.
    if not paths:
        return spark.sparkContext.emptyRDD()
    return spark.sparkContext.union([spark.sparkContext.binaryFiles(p.as_uri(), minPartitions=1)
                                    for p in paths])


def ingest(spark, root):
    paths = sorted((root / 'sftp-drop/upload').glob('CUSTBILL*.dat'))
    for uri, data in read_files(spark, paths).collect():
        source = Path(uri.removeprefix('file:'))
        if not any(row.startswith('TRL') for row in lines(data)):
            raise ValueError(f'incomplete transfer: {source.name}; publish with TRL via atomic rename')
        digest = hashlib.sha256(data).hexdigest()
        atomic(root / 'archive' / (source.name + '.' + digest), data)
        atomic(root / 'incoming' / source.name, data)
        source.unlink()


def parse(spark, root):
    paths = sorted((root / 'incoming').glob('CUSTBILL*.dat'))
    for name, data, errors in read_files(spark, paths).map(parse_file).collect():
        source = root / 'incoming' / name
        raw = source.read_bytes()
        if not any(row.startswith('TRL') for row in lines(raw)):
            raise ValueError(f'incomplete staged transfer: {name}')
        digest = hashlib.sha256(raw).hexdigest()
        ledger = {'file': name, 'sha256': digest, 'errors': errors}
        atomic(root / 'ledger' / (name + '.' + digest + '.json'), json.dumps(ledger).encode())
        if errors:
            atomic(root / 'quarantine' / (name + '.' + digest), raw)
            if os.environ.get('CUSTBILL_STRICT') == '1':
                raise ValueError(f'validation failed: {name}; see ledger')
        atomic(root / 'parsed' / (name[:-4] + '.psv'), data)
        os.replace(source, source.with_suffix('.dat.done'))


def report(spark, root):
    paths = sorted((root / 'parsed').glob('CUSTBILL*.psv'))
    rows = read_files(spark, paths).flatMap(report_inputs).collect()
    data = report_bytes(rows)
    name = 'finance_billing_' + datetime.now().strftime('%Y%m%d')
    for suffix in ('.csv', '.xls'):
        atomic(root / 'reports' / (name + suffix), data)
    destination = Path(os.environ.get('CUSTBILL_DELIVERY_DIR', str(root / 'delivery'))).resolve()
    delivered = destination / (name + '.xls')
    atomic(delivered, data)
    if delivered.read_bytes() != data:
        raise OSError('delivery verification failed')
    receipt = {'sha256': hashlib.sha256(data).hexdigest(), 'destination': str(delivered),
               'distribution': json.loads(os.environ.get('CUSTBILL_DISTRIBUTION', '[]'))}
    atomic(root / 'ledger' / 'delivery.json', json.dumps(receipt).encode())


def retain(root, days):
    if days <= 0:
        return
    cutoff = time.time() - days * 86400
    for ledger in (root / 'ledger').glob('CUSTBILL*.json'):
        entry = json.loads(ledger.read_text())
        name, digest = entry['file'], entry['sha256']
        for path in (root / 'archive' / (name + '.' + digest), root / 'incoming' / (name + '.done')):
            if (path.is_file() and path.stat().st_mtime < cutoff
                    and hashlib.sha256(path.read_bytes()).hexdigest() == digest):
                path.unlink()


def run(stage, root):
    with locked(root):
        os.environ['SPARK_LOCAL_IP'] = '127.0.0.1'
        spark = SparkSession.builder.master('local[*]').appName('ow_tp_custbill').getOrCreate()
        spark.sparkContext.addPyFile(str(Path(__file__).resolve()))
        try:
            for function in ([ingest, parse, report] if stage == 'chain' else
                             [{'ingest': ingest, 'parse': parse, 'report': report}[stage]]):
                function(spark, root)
            retain(root, int(os.environ.get('CUSTBILL_RETENTION_DAYS', '0')))
        finally:
            spark.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('ingest', 'parse', 'report', 'chain'), default='chain', nargs='?')
    args = parser.parse_args()
    run(args.stage, Path(os.environ.get('OTTERWORKS_LEGACY_ROOT', 'custbill-work')).resolve())


if __name__ == '__main__':
    main()
