import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import yaml

from lakehouse.parity.spec import discover as discover_specs
from lakehouse.runtime.layout import ROOT

from .inventory import REPO, discover

STATUSES = ('converted', 'replaced_by_platform', 'retired', 'pending')
NON_DATA_KINDS = {'cron_entry', 'batch_runner', 'spark_submit', 'spark_config', 'etl_config',
                  'informatica_workflow', 'informatica_worklet', 'informatica_task',
                  'informatica_scheduler', 'informatica_config', 'informatica_param'}


def entries(path, key):
    try:
        document = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as exc:
        raise ValueError(f'{path}: invalid YAML: {exc}') from exc
    if not isinstance(document, dict) or not isinstance(document.get(key), list):
        raise ValueError(f'{path}: requires a {key} list')
    result = {}
    for entry in document[key]:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str):
            raise ValueError(f'{path}: each entry requires an id')
        if entry['id'] in result:
            raise ValueError(f'{path}: duplicate id {entry["id"]}')
        result[entry['id']] = entry
    return result


def test_reference(value, root=REPO):
    if not isinstance(value, str) or not value.startswith('test:'):
        return False
    parts = value.removeprefix('test:').split('::')
    path = root / parts[0]
    if (not path.resolve().is_relative_to(root.resolve()) or not path.is_file()
            or not path.name.startswith('test_') or len(parts) < 2 or not parts[-1].startswith('test_')):
        return False
    try:
        node = ast.parse(path.read_text())
    except SyntaxError:
        return False
    for part in parts[1:]:
        node = next((child for child in node.body
                     if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and child.name == part), None)
        if node is None:
            return False
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))


def validate_assumptions(assumptions, inventory, specs, root=REPO):
    errors = []
    for identity, entry in assumptions.items():
        prefix = f'{identity}: '
        if not re.fullmatch(r'A-\d{3,}', identity):
            errors.append(prefix + 'invalid assumption id')
        for field in ('title', 'ambiguity', 'decision', 'rationale', 'verification'):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(prefix + f'missing/non-text {field}')
        if entry.get('risk') not in ('low', 'med', 'high') or entry.get('status') not in ('accepted', 'open'):
            errors.append(prefix + 'invalid risk/status')
        references = entry.get('legacy_objects')
        if not isinstance(references, list) or not references or any(not isinstance(v, str) for v in references):
            errors.append(prefix + 'requires legacy_objects list')
        else:
            for reference in references:
                if reference not in inventory:
                    errors.append(prefix + f'unknown legacy object {reference}')
        sources = entry.get('sources')
        if not isinstance(sources, list) or not sources or any(
                not isinstance(source, str) or not (root / source.split('#')[0]).is_file() for source in sources):
            errors.append(prefix + 'requires existing source citations')
        verification = entry.get('verification', '')
        if isinstance(verification, str) and not (verification in specs or test_reference(verification, root)
                                                or re.fullmatch(r'unverified\s*:\s*\S.*', verification, re.S)):
            errors.append(prefix + 'verification must reference a parity spec, a test, or unverified: reason')
    return errors


def parity_result(identity, specs, evidence):
    if identity not in specs:
        return 'UNKNOWN SPEC'
    path, _ = specs[identity]
    report_path = evidence / 'parity' / f'{identity}.json'
    if not report_path.exists():
        return 'NO EVIDENCE'
    try:
        report = json.loads(report_path.read_text())
        if not isinstance(report, dict):
            return 'INVALID EVIDENCE'
        if report.get('id') != identity or report.get('spec_hash') != hashlib.sha256(path.read_bytes()).hexdigest():
            return 'STALE/INVALID'
        return 'PASS' if report['results']['passed'] is True else 'FAIL'
    except (ValueError, KeyError, TypeError):
        return 'INVALID EVIDENCE'


def string_list(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def validate_coverage(coverage, inventory, specs, assumptions, evidence, strict=False, root=REPO):
    errors = [f'Missing coverage id: {v}' for v in sorted(inventory.keys() - coverage.keys())]
    errors += [f'Unknown coverage id: {v}' for v in sorted(coverage.keys() - inventory.keys())]
    for identity, entry in coverage.items():
        status = entry.get('status')
        if status not in STATUSES:
            errors.append(f'{identity}: invalid status')
        for field in ('targets', 'parity', 'assumptions'):
            if not isinstance(entry.get(field), list) or any(not isinstance(v, str) for v in entry[field]):
                errors.append(f'{identity}: {field} must be a string list')
        if not isinstance(entry.get('notes'), str):
            errors.append(f'{identity}: notes must be text')
        for spec in string_list(entry.get('parity')):
            if spec not in specs:
                errors.append(f'{identity}: unknown parity spec {spec}')
        for reference in string_list(entry.get('assumptions')):
            if reference not in assumptions:
                errors.append(f'{identity}: unknown assumption {reference}')
        if status in ('converted', 'replaced_by_platform') and not entry.get('targets'):
            errors.append(f'{identity}: {status} requires targets')
        if (status == 'replaced_by_platform' and inventory.get(identity, {}).get('kind') in ('cron_entry', 'batch_runner')
                and not test_reference(entry.get('verification'), root)):
            errors.append(f'{identity}: replaced orchestration requires a verification test')
        if status == 'converted':
            passing = [spec for spec in string_list(entry.get('parity')) if spec in specs and
                       parity_result(spec, specs, evidence) == 'PASS' and
                       identity in specs[spec][1]['legacy_objects']]
            kind = inventory.get(identity, {}).get('kind')
            verified = kind in NON_DATA_KINDS and test_reference(entry.get('verification'), root)
            if not passing and not verified:
                errors.append(f'{identity}: converted requires covering PASS parity evidence or a non-data verification test')
        if strict and status == 'pending':
            errors.append(f'{identity}: pending (--strict)')
    return errors


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def render_assumptions(assumptions, errors, destination):
    lines = ['# Migration assumptions', '',
             f'Entries: {len(assumptions)}. Validation errors: {len(errors)}.', '']
    for identity, entry in sorted(assumptions.items()):
        lines += [f'## {identity} — {entry.get("title", "INVALID")}', '']
        for field in ('status', 'risk', 'legacy_objects', 'ambiguity', 'decision', 'rationale', 'verification', 'sources'):
            value = entry.get(field, 'MISSING')
            if isinstance(value, list):
                value = ', '.join(map(str, value))
            lines.append(f'**{field}:** {value}')
            lines.append('')
    if errors:
        lines += ['## Validation errors', ''] + [f'- {error}' for error in errors]
    destination.write_text('\n'.join(lines).rstrip() + '\n')


def render_coverage(coverage, inventory, specs, evidence, errors, destination):
    counts = Counter((obj['kind'], str(coverage.get(identity, {}).get('status', 'missing')))
                     for identity, obj in inventory.items())
    lines = ['# Legacy object coverage', '',
             f'Inventory: {len(inventory)}. Validation errors: {len(errors)}.', '',
             '| Kind | converted | replaced_by_platform | retired | pending | Total |',
             '|---|---:|---:|---:|---:|---:|']
    for kind in sorted({obj['kind'] for obj in inventory.values()}):
        values = [counts[kind, status] for status in STATUSES]
        lines.append('| ' + ' | '.join([kind, *map(str, values), str(sum(n for (k, _), n in counts.items() if k == kind))]) + ' |')
    lines.append('| **TOTAL** | ' + ' | '.join(str(sum(n for (_, s), n in counts.items() if s == status)) for status in STATUSES) + f' | {len(inventory)} |')
    lines += ['', '| ID | Sources | Status | Targets | Parity result | Assumptions |',
              '|---|---|---|---|---|---|']
    for identity, obj in sorted(inventory.items()):
        entry = coverage.get(identity, {})
        sources = ', '.join(f'[{source}](../../{source})' for source in obj['sources'])
        parity = ', '.join(f'{spec}: {parity_result(spec, specs, evidence)}' for spec in string_list(entry.get('parity')))
        verification = entry.get('verification')
        if verification:
            parity += ('; ' if parity else '') + str(verification)
        values = [identity, sources, entry.get('status', 'MISSING'), ', '.join(string_list(entry.get('targets'))),
                  parity or '—', ', '.join(string_list(entry.get('assumptions')))]
        lines.append('| ' + ' | '.join(cell(value) for value in values) + ' |')
    if errors:
        lines += ['', '## Validation errors', ''] + [f'- {error}' for error in errors]
    destination.write_text('\n'.join(lines) + '\n')


def check(strict=False, assumptions_only=False):
    inventory = discover()
    specs = discover_specs()
    assumptions = entries(ROOT / 'assumptions/assumptions.yaml', 'assumptions')
    assumption_errors = validate_assumptions(assumptions, inventory, specs)
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    render_assumptions(assumptions, assumption_errors, evidence / 'ASSUMPTIONS.md')
    print(f'Assumptions: {len(assumptions)} entries, {len(assumption_errors)} errors')
    errors = list(assumption_errors)
    if not assumptions_only:
        coverage = entries(ROOT / 'coverage/coverage.yaml', 'objects')
        coverage_errors = validate_coverage(coverage, inventory, specs, assumptions, evidence, strict)
        render_coverage(coverage, inventory, specs, evidence, coverage_errors, evidence / 'COVERAGE.md')
        print(f'Coverage: {len(inventory)} inventory objects, {len(coverage)} map entries, {len(coverage_errors)} errors')
        for kind, count in sorted(Counter(obj['kind'] for obj in inventory.values()).items()):
            print(f'  {kind}: {count}')
        errors += coverage_errors
    for error in errors:
        print('ERROR: ' + error)
    return 1 if errors else 0
