import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'snowflake'))
import deploy_usage_task as deploy  # noqa: E402


def test_usage_task_runtime_attribution():
    sql = deploy.task_sql('a' * 40, 'SFNFR_20261104-usage-runtime-test')
    assert 'SFNFR_20261104_WH_DOC_USAGE_DASHBOARD' in sql
    assert 'USING CRON 0 * * * * UTC' in sql
    assert 'CHECK_FAULT_SWITCH' in sql
    assert 'CALL SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.RAW.LOAD_RAW()' in sql
    assert 'EXECUTE DBT PROJECT' in sql
    assert 'RECORD_REFRESH' in sql
    assert sql.index('CHECK_FAULT_SWITCH') < sql.index('LOAD_RAW')
    assert sql.index('LOAD_RAW') < sql.index('EXECUTE DBT PROJECT')
    assert sql.index('EXECUTE DBT PROJECT') < sql.index('RECORD_REFRESH')
    assert "'REFRESH_DOC_USAGE_DASHBOARD'" in sql
    assert 'SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS' in sql
    assert 'path:models/doc_usage_dashboard' in sql
    assert '"phase":"runtime"' in sql
    assert '"commit":"' + 'a' * 40 + '"' in sql
    assert 'session_url' not in sql


@pytest.mark.parametrize('commit,run_id', [('', 'run'), ('a' * 40, '')])
def test_usage_task_rejects_missing_attribution(commit, run_id):
    with pytest.raises(deploy.attr.AttributionError):
        deploy.task_sql(commit, run_id)


def test_deployment_uploads_only_dbt_source(tmp_path):
    assert deploy.project_files(tmp_path) == []
    for name in ['dbt_project.yml', 'model.sql', '.gitignore', 'run.py']:
        (tmp_path / name).write_text('')
    assert [file.name for file in deploy.project_files(tmp_path)] == ['dbt_project.yml', 'model.sql']


@pytest.mark.parametrize('state,query_tag,bootstrap,first,error', [
    ('SUCCEEDED', 'runtime-tag', False, False, None),
    ('FAILED', 'runtime-tag', False, False, 'Task failed'),
    ('SUCCEEDED', '', False, True, 'runtime query-tag mismatch'),
    ('SUCCEEDED', None, False, False, 'Missing queries'),
    ('SUCCEEDED', '', True, True, None),
    ('SUCCEEDED', '', True, False, 'runtime query-tag mismatch'),
])
def test_runtime_verification(state, query_tag, bootstrap, first, error):
    now = datetime.now(timezone.utc)

    class Cursor:
        def execute(self, sql, params):
            assert 'TO_TIMESTAMP_LTZ(%s)' in sql
            if 'TASK_HISTORY(' in sql:
                assert 'SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP()' in sql
            if 'QUERY_HISTORY_BY_WAREHOUSE(' in sql:
                assert 'AND ROLE_NAME = %s' in sql
                assert params[-1] == 'SFNFR_20261104_BUILDER'
            self.sql = sql
            return self

        def fetchall(self):
            if 'TASK_HISTORY(' in self.sql:
                return [('TASK', state, now, now, now, 'task-query', None, None)]
            if 'QUERY_HISTORY_BY_SESSION(' in self.sql:
                return [('query' if first else 'earlier-query', 2)]
            text = "alter session set query_tag = 'runtime-tag'" if bootstrap else 'select 1'
            kind = 'ALTER_SESSION' if bootstrap else 'SELECT'
            return [] if query_tag is None else [('query', now, 'BUILDER', kind, text[:60], query_tag, text, 123)]

    args = (Cursor(), deploy.attr.names([deploy.WORKLOAD]), 'DB.ANALYTICS.TASK', 'runtime-tag',
            'SFNFR_20261104_BUILDER', now)
    if error:
        with pytest.raises(AssertionError if state == 'SUCCEEDED' else RuntimeError, match=error):
            deploy.verify_run(*args)
    else:
        result = deploy.verify_run(*args)
        assert result['mismatch_count'] == 0
        assert result['strict_mismatch_count'] == int(bootstrap)


@pytest.mark.parametrize('kind,text,tag,first,expected', [
    ('SELECT', 'select 1', 'runtime-tag', False, True),
    ('ALTER_SESSION', "alter session set query_tag = 'runtime-tag'", '', True, True),
    ('ALTER_SESSION', " ALTER SESSION SET QUERY_TAG='runtime-tag';\n", None, True, True),
    ('ALTER_SESSION', "alter session set query_tag = 'runtime-tag'", '', False, False),
    ('SELECT', "alter session set query_tag = 'runtime-tag'", '', True, False),
    ('ALTER_SESSION', "alter session set query_tag = 'other-tag'", '', True, False),
    ('ALTER_SESSION', "alter session set query_tag = 'RUNTIME-TAG'", '', True, False),
    ('ALTER_SESSION', "alter session set query_tag = 'runtime-tag'; select 1", '', True, False),
    ('ALTER_SESSION', "alter session set query_tag = 'runtime-tag', timezone='UTC'", '', True, False),
    ('ALTER_SESSION', "alter session unset query_tag", '', True, False),
    ('ALTER_SESSION', '', '', True, False),
])
def test_exact_native_bootstrap_exception(kind, text, tag, first, expected):
    assert deploy.query_is_compliant(kind, text, tag, first, 'runtime-tag') is expected


def test_bootstrap_tag_preserves_exact_json_and_sql_escaping():
    tag = '{"run_id":"fixture\'s-A"}'
    sql = 'alter session set query_tag = ' + deploy.attr.sql_string(tag)
    assert deploy.query_is_compliant('ALTER_SESSION', sql, '', True, tag)
    assert not deploy.query_is_compliant('ALTER_SESSION', sql, '', True, tag.lower())


@pytest.mark.parametrize('fail', [False, True])
def test_native_task_fails_closed_on_verification_error(monkeypatch, fail):
    statements = []

    class Cursor:
        def execute(self, sql):
            statements.append(sql)

    def verify(*args):
        if fail:
            raise AssertionError('bad attribution')
        return {'mismatch_count': 0}

    monkeypatch.setattr(deploy, 'verify_run', verify)
    if fail:
        with pytest.raises(AssertionError, match='bad attribution'):
            deploy.verify_or_suspend(Cursor(), {}, 'DB.ANALYTICS.TASK', 'tag', 'BUILDER', None)
        assert statements == ['ALTER TASK DB.ANALYTICS.TASK SUSPEND']
    else:
        assert deploy.verify_or_suspend(Cursor(), {}, 'DB.ANALYTICS.TASK', 'tag', 'BUILDER', None) == {'mismatch_count': 0}
        assert statements == []


def test_deploy_uses_current_named_branch(monkeypatch):
    def branch_output(command, text):
        assert command[-2:] == ['--abbrev-ref', 'HEAD']
        return 'devin/refresh-drill\n'

    monkeypatch.setattr(deploy.subprocess, 'check_output', branch_output)
    assert deploy.current_branch('/repo') == 'devin/refresh-drill'


def test_deploy_refuses_detached_head(monkeypatch):
    monkeypatch.setattr(deploy.subprocess, 'check_output', lambda *args, **kwargs: 'HEAD\n')
    with pytest.raises(ValueError, match='detached'):
        deploy.current_branch('/repo')
