import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from defusedxml import ElementTree as ET
import pytest
from pyspark.sql import types as T
import yaml

from lakehouse.billing import calendar
from lakehouse.billing import spark as billing_spark
from lakehouse.billing.spark_inputs import TABLES
from lakehouse.coverage.checker import entries, parity_result
from lakehouse.orchestration import graph, runner
from lakehouse.parity.spec import discover
from lakehouse.runtime import bootstrap, documents_informatica, documents_spark, users_informatica, users_spark
from lakehouse.runtime.informatica_settings import DEFAULT, resolve
from lakehouse.runtime.layout import DOMAINS, LAYERS, ROOT, initialize
from lakehouse.tests.legacy_dependencies import WAREHOUSE, ancestors, lineage, stages


CONTENT = ROOT.parent / 'etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML'


def daily():
    dag = graph.load()['lakehouse_daily']
    return dag, {node['id']: node for node in dag['nodes']}


def test_daily_chain_read_after_write_and_failure(tmp_path, monkeypatch, capsys):
    dag, nodes = daily()
    all_nodes = [node for config in graph.load().values() for node in config['nodes']]
    mapping = {}
    for stage in stages():
        key = 'cron_entry:warehouse/teradata/jobs/daily_chain#stage=' + stage
        matches = [node['id'] for node in all_nodes if key in node['legacy_objects']]
        assert matches, stage
        mapping[stage] = matches[0]
    assert mapping['generate'] not in nodes
    assert mapping['setup'] == 'initialize'
    writers = {}
    for stage in stages():
        if stage in ('setup', 'generate', 'staging'):
            continue
        reads, writes = lineage(stage)
        assert reads or writes, stage
        target = mapping[stage]
        for table in reads:
            if '.STG_' in table:
                assert 'bronze_' + table.split('.')[0].removeprefix('SFX_').lower() in ancestors(nodes, target)
            if table in writers:
                source = mapping[writers[table]]
                assert source == target or source in ancestors(nodes, target), (writers[table], stage, table)
        for table in writes:
            writers[table] = stage
    storage_writes = lineage('documents/10_storage_monthly')[1]
    assert storage_writes == {'SFX_BILLING.USAGE_DAILY', 'SFX_BILLING.INVOICE_LINE'}
    for stage in ('billing/10_subscription_report', 'billing/11_currency_daily'):
        assert lineage(stage)[0].isdisjoint(storage_writes)
        assert 'dbt_storage_monthly' in ancestors(nodes, mapping[stage])
    monkeypatch.setattr(runner, 'data_root', lambda: tmp_path)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)

    def execute(node, *_):
        if node['id'] == 'dbt_users':
            raise RuntimeError('injected upstream failure')

    monkeypatch.setattr(runner, 'execute', execute)
    assert runner.run(dag, tmp_path, '20261109') == 1
    output = capsys.readouterr().out
    assert 'dbt_documents: BLOCKED' in output and 'dbt_audit: BLOCKED' in output
    assert 'dbt_billing: PASS' in output


@pytest.mark.parametrize('day', ['20261231', '20260101', '20260228', '20240229'])
def test_chain_month_boundary_variables(day, tmp_path, monkeypatch):
    tree = ast.parse((WAREHOUSE / 'jobs/daily_chain').read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'variables')
    namespace = {}
    exec('import datetime as dt\nimport calendar', namespace)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<legacy variables>', 'exec'), namespace)
    expected = namespace['variables'](day, tmp_path)
    actual = calendar.variables(day, tmp_path)
    assert {key: actual[key] for key in expected} == expected
    monkeypatch.setenv('NS', 'shared-date-test')
    assert all(runner.task_environment(day)[key] == value for key, value in expected.items() if key != 'EXPORT_DIR')


def test_chain_invalid_dates():
    for day in ('20260229', '20261301', '', '2026-01-01'):
        with pytest.raises(ValueError):
            calendar.variables(day, Path('.'))


def test_setup_and_fixture_generation(tmp_path, monkeypatch):
    statements = []
    initialize(SimpleNamespace(sql=statements.append))
    assert len(statements) == len(LAYERS) * len(DOMAINS)
    assert all('CREATE DATABASE IF NOT EXISTS' in sql and 'USING' not in sql for sql in statements)
    fake = SimpleNamespace(stop=lambda: statements.append('stopped'))
    monkeypatch.setattr(bootstrap, 'create_session', lambda: fake)
    monkeypatch.setattr('sys.argv', ['bootstrap', '--business-date', '20261109'])
    bootstrap.main()
    assert statements[-1] == 'stopped'
    calls = []
    monkeypatch.setattr(bootstrap, 'generate', lambda *args: calls.append(args))
    monkeypatch.setattr('sys.argv', ['bootstrap', '--business-date', '20261109', '--landing', str(tmp_path)])
    bootstrap.main()
    assert calls == [(200000, 1110, tmp_path, '20261109')]
    monkeypatch.setattr('sys.argv', ['bootstrap', '--business-date', '20261231', '--landing', str(tmp_path),
                                    '--rows', '2', '--seed', '42'])
    bootstrap.main()
    assert calls[-1] == (2, 42, tmp_path, '20261231')
    monkeypatch.setattr('sys.argv', ['bootstrap', '--business-date', '20261109', '--landing', str(tmp_path),
                                    '--rows', '0'])
    bootstrap.main()
    assert calls[-1] == (0, 1110, tmp_path, '20261109')
    monkeypatch.setattr('sys.argv', ['bootstrap', '--business-date', '20261109', '--landing', str(tmp_path),
                                    '--rows', '-1'])
    with pytest.raises(SystemExit):
        bootstrap.main()
    dag = graph.load()['lakehouse_fixture_bootstrap']
    assert dag['schedule'] is None and dag['paused']
    assert '--landing' in dag['nodes'][0]['command']
    assert not any('--landing' in node.get('command', []) and 'lakehouse.runtime.bootstrap' in node['command']
                   for node in daily()[0]['nodes'])


def test_daily_cadence_and_namespace_lock(tmp_path, monkeypatch):
    source = (WAREHOUSE / 'jobs/crontab.example').read_text()
    assert '15 1 * * *' in source and 'flock' in source
    dag, _ = daily()
    assert dag['schedule'] == '@daily' and dag['timezone'] == 'UTC' and dag['catchup'] and dag['paused']
    assert dag['max_active_runs'] == dag['max_active_tasks'] == 1
    monkeypatch.setattr(runner, 'data_root', lambda: tmp_path)
    with runner.namespace_lock():
        with pytest.raises(RuntimeError, match='active pipeline'):
            with runner.namespace_lock():
                pytest.fail('second namespace lease acquired')
    with runner.namespace_lock():
        pass


def test_content_workflow_link_conditions(tmp_path, monkeypatch, capsys):
    tree = ET.parse(CONTENT)
    instances = {element.attrib['NAME']: element.attrib for element in tree.iter('TASKINSTANCE')}
    assert instances['s_m_SFX_TEAM_MEMBER']['ISENABLED'] == 'NO'
    _, nodes = daily()
    mapping = {'Start': 'bronze_users', 's_m_SFX_STG_APP_USER': 'infa_users_app',
               's_m_SFX_APP_USER': 'infa_users_app', 's_m_SFX_ROLE_GRANT': 'infa_users_role_grant',
               's_m_SFX_LOGIN_EVENT': 'infa_users_login_event', 's_m_SFX_STG_DOCUMENT': 'documents_informatica',
               's_m_SFX_DOCUMENT': 'documents_informatica', 's_m_SFX_DOC_SHARE': 'documents_informatica'}
    for link in tree.iter('WORKFLOWLINK'):
        source, target = link.attrib['FROMTASK'], link.attrib['TOTASK']
        if instances[target]['ISENABLED'] == 'NO':
            continue
        assert link.attrib['CONDITION'] == ('' if source == 'Start' else '$'+source+'.Status=SUCCEEDED')
        assert mapping[source] == mapping[target] or mapping[source] in ancestors(nodes, mapping[target])
    assert not any('informatica_session:SFX_CONTENT.s_m_SFX_TEAM_MEMBER' in node['legacy_objects']
                   for node in nodes.values())
    manual = graph.load()['lakehouse_users_infa_team_manual']
    assert manual['paused'] and manual['schedule'] is None
    assert manual['nodes'][1]['specs'] == ['users.infa_team_member']
    source = Path(users_informatica.__file__).read_text()
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'events')
    assert 'team_member' not in ast.get_source_segment(source, function)
    assert ast.get_source_segment(source, function).find("'infa_login_event'") >= 0
    monkeypatch.setattr(runner, 'data_root', lambda: tmp_path)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    def execute(node, *_):
        if node['id'] == 'infa_users_app':
            raise RuntimeError('app session failure')
    monkeypatch.setattr(runner, 'execute', execute)
    assert runner.run(daily()[0], tmp_path, '20261109') == 1
    output = capsys.readouterr().out
    assert 'infa_users_role_grant: BLOCKED' in output and 'documents_informatica: BLOCKED' in output


def test_content_scheduler_replacement():
    tree = ET.parse(CONTENT)
    scheduler = next(tree.iter('SCHEDULER'))
    text = ET.tostring(scheduler).decode()
    assert '02:15' in text
    assert daily()[0]['schedule'] == '@daily' and daily()[0]['catchup']


def test_parameter_precedence(tmp_path):
    legacy = ROOT.parent / 'etl/informatica/params/sfx_d1110_daily.par'
    for path in (legacy, DEFAULT):
        assert resolve('SFX_AUDIT', 'wf_SFX_AUDIT_DAILY', path=path)['$$ARCHIVE_DAYS'] == '730'
        assert resolve('SFX_AUDIT', 'wf_SFX_AUDIT_DAILY', 's_m_SFX_AUDIT_EVENT_ARCHIVE', path=path)['$$ARCHIVE_DAYS'] == '2555'
        assert resolve('SFX_CONTENT', 'wf_SFX_CONTENT_DAILY', path=path, day='20260101')['$$LOAD_DATE'] == '20260101'
    path = tmp_path / 'precedence.par'
    path.write_text('[Global]\nx=global\ny=global\n[F.WF:w]\nx=workflow\n[F.WF:w.ST:s]\nx=session\n')
    assert resolve('F', 'w', 's', path=path) == {'x': 'session', 'y': 'global'}
    assert resolve('F', 'w', 'other', path=path)['x'] == 'workflow'
    path.write_text('')
    assert resolve('F', 'w', path=path) == {}
    path.write_text('not a parameter section')
    with pytest.raises(ValueError):
        resolve('F', 'w', path=path)
    with pytest.raises(FileNotFoundError):
        resolve('F', 'w', path=tmp_path / 'missing')


def test_content_session_error_behavior(tmp_path):
    config = next(element for element in ET.parse(CONTENT).iter('CONFIG')
                  if element.attrib['NAME'] == 'default_session_config')
    options = {element.attrib.get('NAME'): element.attrib.get('VALUE') for element in config.iter('ATTRIBUTE')}
    assert options['Stop on errors'] == '0'
    assert all(options[name] == 'Stop' for name in (
        'On Stored Procedure error', 'On Pre-session command task error', 'On Pre-Post SQL error'))
    malformed = dict(zip(documents_informatica.DOCUMENT, ['bad', '1', '1', '1', 'Bad', '2026-11-09', 'ACTIVE', 'txt']))
    valid = dict(zip(documents_informatica.DOCUMENT, ['2', '1', '1', '1', 'Good', '2026-11-09', 'ACTIVE', 'txt']))
    result = documents_informatica.convert([malformed, valid], [], [dict(user_id=1, status_cd='ACTIVE')], [])
    assert [row['document_id'] for row in result['document']] == [2]
    assert result['metrics'][0]['transformation_errors'] == 1
    with pytest.raises(FileNotFoundError):
        documents_informatica.read_feed(tmp_path / 'absent', documents_informatica.DOCUMENT)
    with pytest.raises(RuntimeError, match='SQL failure'):
        initialize(SimpleNamespace(sql=lambda _: (_ for _ in ()).throw(RuntimeError('SQL failure'))))


def test_connection_uses_namespace_delta(tmp_path, monkeypatch):
    legacy = yaml.safe_load((ROOT.parent / 'etl/informatica/config/connections.yaml').read_text())
    assert legacy['connections']['TD_SFX_EDW']['default_database'] == 'SFX_BILLING'
    for key, variable in {'host': 'TD_HOST', 'port': 'TD_PORT', 'database': 'TD_DB',
                          'user': 'TD_USER', 'password': 'TD_PASSWORD'}.items():
        assert legacy['connections']['TD_SFX_EDW'][key] == '${' + variable + '}'
    monkeypatch.setenv('NS', 'shared-connection-test')
    statements = []
    initialize(SimpleNamespace(sql=statements.append))
    assert all('shared-connection-test/delta/' in sql and 'PASSWORD' not in sql for sql in statements)
    assert {sql.split()[5] for sql in statements} == {f'{layer}_{domain}' for layer in LAYERS for domain in DOMAINS}


def test_spark_registry_complete():
    jobs = (ROOT.parent / 'etl/spark/jobs.txt').read_text().splitlines()
    assert len(jobs) == len(set(jobs)) == 30
    coverage = entries(ROOT / 'coverage/coverage.yaml', 'objects')
    specs = discover()
    dags = graph.load()
    for job in jobs:
        identity = 'spark_job:' + job
        assert coverage[identity]['status'] in ('converted', 'replaced_by_platform')
        parity = set(coverage[identity]['parity'])
        assert parity and all(parity_result(spec, specs, ROOT / 'evidence') == 'PASS' for spec in parity)
        matches = [(dag, node) for dag in dags.values() for node in dag['nodes'] if identity in node['legacy_objects']]
        assert len(matches) == 1, job
        dag, task = matches[0]
        nodes = {node['id']: node for node in dag['nodes']}
        connected = {spec for node in dag['nodes'] if node['kind'] == 'parity'
                     and task['id'] in ancestors(nodes, node['id'])
                     for spec in node.get('specs', [node.get('spec')])}
        assert parity <= connected, job


def test_common_package_imports(monkeypatch):
    monkeypatch.setenv('NS', 'shared-package-test')
    assert runner.task_environment('20261109')['PYTHONPATH'] == str(ROOT.parent)
    modules = {node['command'][2] for dag in graph.load().values() for node in dag['nodes']
               if any(identity.startswith('spark_job:') for identity in node['legacy_objects'])
               and node['kind'] == 'export' and node.get('command', [None, None])[1] == '-m'}
    assert modules
    assert all(importlib.util.find_spec(module) is not None for module in modules)


def test_common_schemas_typed_reads():
    from etl.spark.jobs.py.common import schemas as legacy
    from lakehouse.runtime import spark_schemas as native
    for registry in ('TABLES', 'SCHEMAS', 'DAILY_TABLES', 'DIMENSION_ROWS'):
        assert getattr(native, registry) == getattr(legacy, registry)
    SCHEMAS = native.SCHEMAS
    mapping = {'BIGINT': T.LongType(), 'TEXT': T.StringType(), 'DATE': T.DateType(), 'TIMESTAMP': T.TimestampType()}
    for table in TABLES:
        actual = billing_spark.schema(table)
        assert [field.name for field in actual] == [name.lower() for name, _ in SCHEMAS[table]]
        for field, (_, kind) in zip(actual, SCHEMAS[table]):
            expected = mapping.get(kind) if not kind.startswith('DECIMAL') else T.DecimalType(
                *map(int, kind[8:-1].split(',')))
            assert field.dataType == expected and field.nullable


@pytest.mark.parametrize('library', ['python', 'scala'])
def test_common_runtime_reads_and_write_modes(tmp_path, monkeypatch, library):
    legacy = ROOT.parent / ('etl/spark/scala/src/main/scala/sfx/BatchSupport.scala' if library == 'scala'
                            else 'etl/spark/jobs/py/common/runtime.py')
    assert ('inferSchema' if library == 'scala' else 'DecimalType') in legacy.read_text()
    with pytest.raises(FileNotFoundError, match='Missing Spark landing'):
        users_spark.read_inputs(None, tmp_path)
    writes = []

    class Frame:
        @property
        def write(self):
            return self

        def format(self, value):
            writes.append(('format', value))
            return self

        def mode(self, value):
            writes.append(('mode', value))
            return self

        def save(self, value):
            writes.append(('save', value))

    frame = Frame()
    monkeypatch.setenv('NS', 'shared-write-test')
    monkeypatch.setattr(users_spark, 'read_inputs', lambda *a: None)
    monkeypatch.setattr(users_spark, 'outputs', lambda _: [('library_test', frame)])
    users_spark.run(SimpleNamespace(sql=lambda _: None), tmp_path)
    assert ('format', 'delta') in writes and ('mode', 'overwrite') in writes
    assert any('/gold/users/library_test' in value for key, value in writes if key == 'save')
    calls = []

    class Reader:
        def schema(self, value):
            calls.append(('schema', value))
            return self

        def option(self, key, value):
            calls.append((key, value))
            return self

        def csv(self, value):
            return frame

    billing_spark.inputs(SimpleNamespace(read=Reader()), tmp_path, 'INVOICE_HDR')
    assert isinstance(calls[0][1], T.StructType)
    assert ('sep', '|') in calls and ('header', True) in calls
    assert not any(key == 'inferSchema' for key, _ in calls)


def test_spark_settings_replace_event_history(monkeypatch):
    from lakehouse.runtime import session
    source = (ROOT.parent / 'etl/spark/conf/spark-defaults.conf').read_text()
    assert 'spark.eventLog.enabled true' in source and 'spark.history.fs.logDirectory' in source
    configurations = {}

    class Builder:
        def appName(self, value):
            return self

        def master(self, value):
            assert value == 'local[2]'
            return self

        def config(self, key, value):
            configurations[key] = value
            return self

        def enableHiveSupport(self):
            return self

        def getOrCreate(self):
            return SimpleNamespace(sparkContext=SimpleNamespace(setLogLevel=lambda _: None))

    monkeypatch.setenv('NS', 'shared-config-test')
    monkeypatch.setattr(session, 'SparkSession', SimpleNamespace(builder=Builder()))
    monkeypatch.setattr(session, 'configure_spark_with_delta_pip', lambda builder: builder)
    monkeypatch.setattr(session, 'initialize', lambda _: None)
    session.create_session()
    assert configurations['spark.sql.session.timeZone'] == 'UTC'
    assert configurations['spark.sql.ansi.enabled'] == 'true'
    assert configurations['spark.sql.extensions'] == 'io.delta.sql.DeltaSparkSessionExtension'
    assert not any(key.startswith(('spark.eventLog', 'spark.history')) for key in configurations)
