import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
import zlib

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml'
SCHEMAS = {'summary': 'PolicySummary', 'values': 'PolicyValue', 'funds': 'PolicyFunds'}
STATUSES = {'00': (200, None), '04': (404, 'policy.inquiry.notFound'),
            '08': (400, 'policy.inquiry.invalidPolicyNumber'), '96': (503, 'policy.inquiry.unavailable')}


def canonical(value):
    if not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError('contract number must contain digits only')
    return str(int(value))


def transform(value, rule, entry):
    if rule == 'identity':
        return str(value)
    if rule == 'contract_number':
        return canonical(value)
    if rule == 'yyyymmdd_to_date':
        if not re.fullmatch(r'[0-9]{8}', value):
            raise ValueError('expected YYYYMMDD')
        return datetime.strptime(value, '%Y%m%d').date().isoformat()
    if rule == 'implied_decimal':
        if not re.fullmatch(r'[0-9]+', value):
            raise ValueError('expected implied decimal digits')
        return Decimal(value).scaleb(-entry['scale'])
    if rule == 'enum_map':
        result = entry['map'][value]
        if result is None:
            raise ValueError(f'unmapped enum {value}')
        return result
    raise ValueError(f'unknown transform {rule}')


def pointer(body, path):
    for token in path.lstrip('/').split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        body = body[int(token)] if isinstance(body, list) else body[token]
    return body


def validator(spec, name):
    return Draft202012Validator({'$ref': f'#/components/schemas/{name}',
                                 'components': spec['components']}, format_checker=FormatChecker())


def compare(case, status, body, entries, spec):
    operation = case['operation']
    entries = [e for e in entries if e['operation'] == operation]
    legacy = case['body']
    errors, signoffs, provisional = [], [], []
    expected, code = STATUSES[legacy['RTN_CD']]
    for e in entries:
        if e['rule'] == 'enum_map' and legacy.get(e['legacy_field']) in e.get('signoff_values', []):
            expected, code = 422, 'policy.status.unmapped'
            signoffs.append(e['signoff_id'])
    schema = SCHEMAS[operation] if 200 <= status < 300 else 'Error'
    schema_errors = [f"/{'/'.join(map(str, e.absolute_path))}: {e.message}"
                     for e in validator(spec, schema).iter_errors(body)]
    if status != expected:
        errors.append(f'HTTP status: expected {expected}, got {status}')
    if expected != 200:
        if not isinstance(body, dict) or body.get('code') != code:
            errors.append(f'Error.code: expected {code}')
    elif status == 200:
        if isinstance(body, dict) and 'policyNumber' in body:
            errors.append('C-2: policyNumber must not be echoed in body')
        for e in entries:
            rule = e['rule']
            if rule == 'dropped' or e['legacy_field'] == 'RTN_CD':
                continue
            target = e['iri_element']
            try:
                if e['status'] == 'provisional':
                    paths = ([target.replace('/i/', f'/{i}/') for i in range(int(legacy.get('FUND_CNT', 0)))]
                             if '/i/' in target else [target])
                    for path in paths:
                        pointer(body, path)
                        provisional.append(path)
                    if rule == 'provisional':
                        continue
                if rule == 'count':
                    count = int(legacy[e['legacy_field']])
                    for path in e['targets']:
                        if pointer(body, path) != count:
                            errors.append(f'{path}: expected {count}')
                    if pointer(body, '/startIndex') != 0 or len(pointer(body, '/funds')) != count:
                        errors.append('funds envelope: expected startIndex 0 and FUND_CNT rows')
                    continue
                if rule == 'indexed_list':
                    for i in range(int(legacy['FUND_CNT'])):
                        field = e['legacy_field'].replace('_nn', f'_{i + 1:02d}')
                        path = target.replace('/i/', f'/{i}/')
                        expected_value = transform(legacy[field], e['item_rule'], e)
                        if pointer(body, path) != expected_value:
                            errors.append(f'{path}: expected {expected_value}, got {pointer(body, path)}')
                    continue
                expected_value = transform(legacy[e['legacy_field']], rule, e)
                actual = canonical(case['policy_number']) if rule == 'contract_number' else pointer(body, target)
                if actual != expected_value:
                    errors.append(f'{target}: expected {expected_value}, got {actual}')
            except (KeyError, ValueError, TypeError, IndexError) as error:
                errors.append(f'{target}: {error}')
    return {'case_id': case['case_id'], 'policy_number': case['policy_number'],
            'status': status, 'outcome': 'FAIL' if errors or schema_errors else 'SIGNOFF' if signoffs else 'PASS',
            'errors': errors, 'schema_errors': schema_errors, 'signoffs': signoffs,
            'provisional_elements_emitted': sorted(set(provisional))}


def run(args):
    entries = yaml.safe_load((ROOT / 'lineage/lineage.yaml').read_text())['entries']
    spec = yaml.safe_load(SPEC.read_text())
    cases = json.loads((args.frozen / f'{args.operation}.json').read_text())
    url = (args.iri_url or f'http://127.0.0.1:{19080 + zlib.crc32(args.namespace.encode()) % 1000}').rstrip('/')
    results = []
    for case in cases:
        try:
            try:
                response = urllib.request.urlopen(f"{url}/v1/policies/{case['policy_number']}/{args.operation}", timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = json.loads(response.read().decode('utf-8'), parse_float=Decimal)
                result = compare(case, response.status, body, entries, spec)
        except (OSError, ValueError, KeyError, TypeError) as error:
            result = {'case_id': case['case_id'], 'outcome': 'FAIL', 'errors': [str(error)],
                      'schema_errors': [], 'provisional_elements_emitted': []}
        results.append(result)
    counts = Counter(r['outcome'] for r in results)
    summary = {'cases': len(results), **{k: counts[k] for k in ('PASS', 'FAIL', 'SIGNOFF')},
               'schema-invalid': sum(bool(r['schema_errors']) for r in results),
               'provisional_elements_emitted': sorted({p for r in results for p in r['provisional_elements_emitted']})}
    if not cases:
        raise ValueError('frozen case set is empty')
    args.reports.mkdir(parents=True, exist_ok=True)
    report = {'operation': args.operation, 'summary': summary, 'results': results}
    (args.reports / f'{args.operation}.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = [f'# {args.operation} parity', '', json.dumps(summary), '', '| Case | Outcome | Details |', '| --- | --- | --- |']
    for r in results:
        details = '; '.join(r['errors'] + r['schema_errors'] + r.get('signoffs', [])).replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| {r['case_id']} | {r['outcome']} | {details} |")
    (args.reports / f'{args.operation}.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(summary))
    return int(bool(summary['FAIL'] or summary['schema-invalid']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('namespace')
    parser.add_argument('operation', choices=SCHEMAS)
    parser.add_argument('--iri-url')
    parser.add_argument('--frozen', type=Path, default=ROOT / 'parity/frozen')
    parser.add_argument('--reports', type=Path, default=ROOT / 'parity/reports')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.namespace):
        parser.error('invalid namespace')
    try:
        raise SystemExit(run(args))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Parity failed: {error}\n')


if __name__ == '__main__':
    main()
