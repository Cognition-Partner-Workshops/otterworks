import ast
import hashlib
import importlib
import json
import xml.etree.ElementTree as ET

import pytest

from lakehouse.coverage import checker
from lakehouse.coverage.inventory import REPO, discover
from lakehouse.runtime.layout import ROOT


PILOT = 'teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT'
SPEC = 'billing.customer_account'
TEST = 'test:lakehouse/tests/test_coverage.py::test_inventory_from_repository'


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_inventory_from_repository():
    inventory = discover()
    assert inventory == discover()
    assert all(identity == f'{obj["kind"]}:{obj["name"]}' for identity, obj in inventory.items())
    assert all((REPO / source.split('#')[0]).is_file()
               for obj in inventory.values() for source in obj['sources'])
    jobs = {name.strip() for name in (REPO / 'etl/spark/jobs.txt').read_text().splitlines()
            if name.strip() and not name.startswith('#')}
    assert {obj['name'] for obj in inventory.values() if obj['kind'] == 'spark_job'} == jobs
    python = {path.stem for path in (REPO / 'etl/spark/jobs/py').glob('*.py') if path.name != '__init__.py'}
    assert len(python) == 24
    assert python <= jobs
    assert {obj['name'] for obj in inventory.values() if obj.get('language') == 'python'} == python
    scala = [path for path in (REPO / 'etl/spark/scala/src/main/scala').rglob('*.scala')
             if 'def main(' in path.read_text()]
    assert len(scala) == sum(obj.get('language') == 'scala' for obj in inventory.values())
    assert 'spark_job:docs_folder_legacy_report' in inventory
    assert any(obj.get('disabled') and 'docs_folder_legacy_report' in
               (REPO / obj['source'].split('#')[0]).read_text().splitlines()[int(obj['source'].split('#L')[1]) - 1]
               for obj in inventory.values() if obj['kind'] == 'cron_entry' and '#L' in obj['source'])
    for kind, folder, suffix in (('fastload', 'load/fastload', '*.fl'), ('tpt', 'load/tpt', '*.tpt'),
                                  ('teradata_macro', 'macros', '*.sql'), ('teradata_procedure', 'procedures', '*.sql')):
        assert sum(obj['kind'] == kind for obj in inventory.values()) == len(list((REPO / 'warehouse/teradata' / folder).glob(suffix)))
    for tag in ('MAPPING', 'WORKFLOW', 'SESSION'):
        names = set()
        for path in (REPO / 'etl/informatica/repository').rglob('*'):
            if path.suffix.lower() == '.xml':
                for folder in ET.parse(path).getroot().iter('FOLDER'):
                    names.update(folder.attrib['NAME'] + '.' + element.attrib['NAME'] for element in folder.iter(tag))
        assert names == {obj['name'] for obj in inventory.values() if obj['kind'] == 'informatica_' + tag.lower()}
    for name in ('CUSTOMER_ACCOUNT_HIST', 'ACCOUNT_HIST_BATCH'):
        assert 'teradata_table:SFX_BILLING.' + name in inventory
    tree = ast.parse((REPO / 'warehouse/teradata/jobs/daily_chain').read_text())
    stages = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('CORE', 'REPORTS') for t in node.targets):
            stages.update(ast.literal_eval(node.value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'stage' and isinstance(node.args[0], ast.Constant):
            stages.add(node.args[0].value)
    assert {identity.split('#stage=')[1] for identity in inventory if '#stage=' in identity} == stages


def test_inventory_empty_and_new_sources(tmp_path):
    assert discover(tmp_path) == {}
    sql = 'warehouse/teradata/ddl/new.sql'
    write(tmp_path, sql, '-- CREATE TABLE X.FAKE (n INT);\nCREATE MULTISET TABLE X.NEW (n INT);\nREPLACE VIEW X.V AS SELECT * FROM X.NEW;')
    write(tmp_path, 'warehouse/teradata/scripts/new.bteq', 'SELECT * FROM X.V;')
    write(tmp_path, 'consumers/partner-extract/sql/new.sql', 'SELECT * FROM X.NEW;')
    write(tmp_path, 'warehouse/teradata/dbql/read.bteq', 'SELECT * FROM DBC.QryLogV;')
    write(tmp_path, 'warehouse/teradata/macros/new.sql', 'REPLACE MACRO X.M AS (SELECT 1;);')
    write(tmp_path, 'warehouse/teradata/procedures/new.sql', 'CREATE PROCEDURE X.P() BEGIN END;')
    write(tmp_path, 'etl/scripts/new.py', 'print(1)')
    write(tmp_path, 'etl/spark/jobs.txt', '# disabled_job\nnew_job\n')
    write(tmp_path, 'etl/spark/jobs/py/new_job.py', 'print(1)')
    write(tmp_path, 'etl/spark/scala/src/main/scala/New.scala', 'object New { def main(args: Array[String]): Unit = {} }')
    write(tmp_path, 'etl/crontab', '# comment\n# 0 1 * * * disabled_job\n0 2 * * * new_job\n')
    write(tmp_path, 'consumers/registry.yaml', 'consumers: [{name: new, path: consumers/new}]')
    write(tmp_path, 'consumers/bi/new.pq', 'let x = 1 in x')
    write(tmp_path, 'etl/informatica/params/empty.par', '# description only')
    write(tmp_path, 'etl/informatica/params/logic.par', '$$FILTER=X')
    write(tmp_path, 'etl/informatica/config/connection.yaml', 'connections: {pure_endpoint: {host: example}, logical: {default_database: X}}')
    xml = '<POWERMART><FOLDER NAME="X"><MAPPING NAME="M"/><WORKFLOW NAME="W"><TASK NAME="Start"/></WORKFLOW><WORKLET NAME="L"><TASK NAME="Start"/></WORKLET></FOLDER></POWERMART>'
    write(tmp_path, 'etl/informatica/repository/export.XML', xml)
    write(tmp_path, 'etl/informatica/repository/duplicate.xml', xml)
    inventory = discover(tmp_path)
    assert 'teradata_table:X.NEW' in inventory and 'teradata_table:X.FAKE' not in inventory
    assert inventory['teradata_view:X.V']['source'] == sql + '#L3'
    assert len(inventory['spark_job:new_job']['sources']) == 2
    assert inventory['spark_job:New']['language'] == 'scala'
    assert len(inventory['informatica_mapping:X.M']['sources']) == 2
    assert {'informatica_task:X.W.Start', 'informatica_task:X.L.Start'} <= inventory.keys()
    assert sum(obj['kind'] == 'informatica_param' for obj in inventory.values()) == 1
    assert sum(obj['kind'] == 'informatica_config' for obj in inventory.values()) == 1
    assert any(obj.get('disabled') for obj in inventory.values())
    original_ids = set(inventory)
    write(tmp_path, 'etl/crontab', '# inserted line\n# comment\n# 0 1 * * * disabled_job\n0 2 * * * new_job\n')
    assert original_ids == discover(tmp_path).keys()


@pytest.fixture
def setup_map(tmp_path):
    spec_path = write(tmp_path, 'spec.yaml', 'pilot spec')
    inventory = {PILOT: {'kind': 'teradata_table'}}
    coverage = {PILOT: {'id': PILOT, 'status': 'converted', 'targets': ['model.sql'],
                        'parity': [SPEC], 'assumptions': ['A-001'], 'notes': ''}}
    specs = {SPEC: (spec_path, {'legacy_objects': [PILOT]})}
    assumptions = {'A-001': {'id': 'A-001', 'title': 'Example', 'legacy_objects': [PILOT],
                            'ambiguity': 'Ambiguity', 'decision': 'Decision', 'rationale': 'Rationale',
                            'risk': 'med', 'verification': SPEC, 'status': 'accepted', 'sources': ['spec.yaml']}}
    report = {'id': SPEC, 'spec_hash': hashlib.sha256(spec_path.read_bytes()).hexdigest(), 'results': {'passed': True}}
    report_path = write(tmp_path, 'evidence/parity/' + SPEC + '.json', json.dumps(report))
    return inventory, coverage, specs, assumptions, tmp_path / 'evidence', report_path


def validate(setup_map, strict=False):
    inventory, coverage, specs, assumptions, evidence, _ = setup_map
    return checker.validate_coverage(coverage, inventory, specs, assumptions, evidence, strict)


def test_seed_statuses_and_assumption_links():
    inventory = discover()
    coverage = checker.entries(ROOT / 'coverage/coverage.yaml', 'objects')
    assumptions = checker.entries(ROOT / 'assumptions/assumptions.yaml', 'assumptions')
    assert inventory.keys() == coverage.keys()
    for identity, entry in coverage.items():
        kind = inventory[identity]['kind']
        assert entry['status'] == ('converted' if identity == PILOT else
                                  'replaced_by_platform' if kind in ('fastload', 'tpt') or
                                  identity == 'cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging' else 'pending')
        assert set(entry['assumptions']) == {key for key, assumption in assumptions.items()
                                            if identity in assumption['legacy_objects']}


def test_coverage_normal_empty_and_strict(setup_map):
    assert validate(setup_map) == []
    assert checker.validate_coverage({}, {}, {}, {}, setup_map[4], strict=True) == []
    setup_map[1][PILOT]['status'] = 'pending'
    assert validate(setup_map) == []
    assert any('pending (--strict)' in error for error in validate(setup_map, strict=True))


@pytest.mark.parametrize('field,value,error', [
    ('status', 'unknown', 'invalid status'), ('targets', [], 'requires targets'),
    ('parity', ['missing'], 'unknown parity spec'), ('assumptions', ['missing'], 'unknown assumption'),
    ('parity', [], 'converted requires'), ('notes', None, 'notes must be text'),
    ('parity', None, 'parity must be a string list'), ('parity', [{}], 'parity must be a string list'),
    ('assumptions', [{}], 'assumptions must be a string list'), ('targets', 1, 'targets must be a string list'),
])
def test_coverage_invalid_fields(setup_map, field, value, error):
    setup_map[1][PILOT][field] = value
    assert any(error in line for line in validate(setup_map))


def test_coverage_missing_extra_and_noncovering_spec(setup_map):
    inventory, coverage, specs, _, _, _ = setup_map
    entry = coverage.pop(PILOT)
    coverage['extra:object'] = entry
    errors = validate(setup_map)
    assert any('Missing coverage id' in error for error in errors)
    assert any('Unknown coverage id' in error for error in errors)
    coverage[PILOT] = coverage.pop('extra:object')
    specs[SPEC][1]['legacy_objects'] = ['other:object']
    assert any('converted requires' in error for error in validate(setup_map))


@pytest.mark.parametrize('report,result', [
    ({'id': SPEC, 'spec_hash': 'old', 'results': {'passed': True}}, 'STALE/INVALID'),
    ({'id': 'other', 'results': {'passed': True}}, 'STALE/INVALID'),
    ([], 'INVALID EVIDENCE'), ('invalid json', 'INVALID EVIDENCE'),
    ({'results': {'passed': False}}, 'FAIL'), ({'results': {}}, 'INVALID EVIDENCE'),
    ({'results': {'passed': 'true'}}, 'FAIL'),
])
def test_converted_evidence_must_be_current_pass(setup_map, report, result):
    _, _, specs, _, evidence, report_path = setup_map
    if isinstance(report, dict) and 'id' not in report:
        report.update(id=SPEC, spec_hash=hashlib.sha256(specs[SPEC][0].read_bytes()).hexdigest())
    report_path.write_text(report if isinstance(report, str) else json.dumps(report))
    assert checker.parity_result(SPEC, specs, evidence) == result
    assert any('converted requires' in error for error in validate(setup_map))


def test_missing_evidence_and_changed_spec(setup_map):
    _, _, specs, _, evidence, report_path = setup_map
    specs[SPEC][0].write_text('changed spec')
    assert checker.parity_result(SPEC, specs, evidence) == 'STALE/INVALID'
    report_path.unlink()
    assert checker.parity_result(SPEC, specs, evidence) == 'NO EVIDENCE'
    assert checker.parity_result('unknown', specs, evidence) == 'UNKNOWN SPEC'
    assert any('converted requires' in error for error in validate(setup_map))


def test_verification_only_for_non_data_objects(setup_map):
    inventory, coverage, _, _, _, _ = setup_map
    coverage[PILOT].update(parity=[], verification=TEST)
    assert any('converted requires' in error for error in validate(setup_map))
    inventory[PILOT]['kind'] = 'cron_entry'
    assert validate(setup_map) == []
    coverage[PILOT]['verification'] = TEST + '_missing'
    assert any('converted requires' in error for error in validate(setup_map))
    assert not checker.test_reference('test:lakehouse/tests/test_coverage.py::write')
    assert not checker.test_reference('test:../test_missing.py::test_x')
    coverage[PILOT].update(status='replaced_by_platform', verification=None)
    assert any('replaced orchestration requires' in error for error in validate(setup_map))
    coverage[PILOT]['verification'] = TEST
    assert validate(setup_map) == []


@pytest.mark.parametrize('field,value,error', [
    ('title', '', 'missing/non-text title'), ('risk', 'critical', 'invalid risk/status'),
    ('status', 'done', 'invalid risk/status'), ('legacy_objects', [], 'requires legacy_objects'),
    ('legacy_objects', ['missing:object'], 'unknown legacy object'), ('legacy_objects', [1], 'requires legacy_objects'),
    ('sources', ['missing.sql'], 'requires existing source citations'), ('sources', None, 'requires existing source citations'),
    ('verification', 'unverified', 'verification must reference'), ('verification', 'missing_spec', 'verification must reference'),
    ('verification', 'test:missing.py::test_x', 'verification must reference'),
    ('decision', None, 'missing/non-text decision'), ('verification', [], 'missing/non-text verification'),
])
def test_assumptions_invalid_fields(setup_map, field, value, error):
    inventory, _, specs, assumptions, evidence, _ = setup_map
    assumptions['A-001'][field] = value
    assert any(error in line for line in checker.validate_assumptions(assumptions, inventory, specs, evidence.parent))


def test_assumptions_normal_empty_and_id(setup_map):
    inventory, _, specs, assumptions, evidence, _ = setup_map
    assert checker.validate_assumptions({}, inventory, specs) == []
    assert checker.validate_assumptions(assumptions, inventory, specs, evidence.parent) == []
    assumptions['A-001']['verification'] = 'unverified: native runtime not available'
    assert checker.validate_assumptions(assumptions, inventory, specs, evidence.parent) == []
    assumptions['A-001'].update(verification=TEST, sources=['warehouse/teradata/ddl/billing/00_tables.sql'])
    assert checker.validate_assumptions(assumptions, inventory, specs) == []
    assumptions['A-001'].update(verification=SPEC, sources=['spec.yaml'])
    assumptions['bad'] = assumptions.pop('A-001')
    assert any('invalid assumption id' in error for error in checker.validate_assumptions(assumptions, inventory, specs, evidence.parent))


@pytest.mark.parametrize('document,error', [
    ('{}', 'requires a objects list'), ('objects: [1]', 'each entry requires an id'),
    ('objects: [{id: A}, {id: A}]', 'duplicate id A'),
])
def test_entry_schema_and_duplicate_ids(tmp_path, document, error):
    path = write(tmp_path, 'map.yaml', document)
    with pytest.raises(ValueError, match=error):
        checker.entries(path, 'objects')


def test_render_and_cli_failure_modes(tmp_path, setup_map, monkeypatch, capsys):
    inventory, coverage, specs, assumptions, _, _ = setup_map
    inventory[PILOT].update(name='Example', source='spec.yaml', sources=['spec.yaml'])
    monkeypatch.setattr(checker, 'ROOT', tmp_path)
    monkeypatch.setattr(checker, 'discover', lambda: inventory)
    monkeypatch.setattr(checker, 'discover_specs', lambda: specs)
    monkeypatch.setattr(checker, 'entries', lambda _, key: assumptions if key == 'assumptions' else coverage)
    assumptions['A-001']['sources'] = ['warehouse/teradata/ddl/billing/00_tables.sql']
    assert checker.check() == 0
    assert '| **TOTAL** | 1 | 0 | 0 | 0 | 1 |' in (tmp_path / 'evidence/COVERAGE.md').read_text()
    assert 'Entries: 1. Validation errors: 0.' in (tmp_path / 'evidence/ASSUMPTIONS.md').read_text()
    coverage[PILOT].update(status='pending', parity=None, targets=None, assumptions=[{}])
    assert checker.check(strict=True) == 1
    assert 'pending (--strict)' in (tmp_path / 'evidence/COVERAGE.md').read_text()
    assert checker.check(assumptions_only=True) == 0
    assert 'Coverage: 1 inventory objects, 1 map entries, 0 errors' in capsys.readouterr().out
    for name in ('lakehouse.coverage.__main__', 'lakehouse.assumptions.__main__'):
        module = importlib.import_module(name)
        monkeypatch.setattr('sys.argv', [name, 'check'])
        monkeypatch.setattr(module, 'check', lambda **_: 1)
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert exc.value.code == 1
        def invalid(**_):
            raise ValueError('invalid input schema')
        monkeypatch.setattr(module, 'check', invalid)
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert exc.value.code == 2
