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
    assert 'CALL SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.RAW.LOAD_RAW()' in sql
    assert 'EXECUTE DBT PROJECT' in sql
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


@pytest.mark.parametrize('state,query_tag,error', [
    ('SUCCEEDED', 'runtime-tag', None),
    ('FAILED', 'runtime-tag', 'Task failed'),
    ('SUCCEEDED', '', 'runtime query-tag mismatch'),
    ('SUCCEEDED', None, 'Missing queries'),
])
def test_runtime_verification(state, query_tag, error):
    now = datetime.now(timezone.utc)

    class Cursor:
        def execute(self, sql, params):
            assert 'TO_TIMESTAMP_LTZ(%s)' in sql
            if 'TASK_HISTORY(' in sql:
                assert 'SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP()' in sql
            self.sql = sql
            return self

        def fetchall(self):
            if 'TASK_HISTORY(' in self.sql:
                return [('TASK', state, now, now, now, 'task-query', None, None)]
            return [] if query_tag is None else [('query', now, 'BUILDER', 'SELECT', 'select 1', query_tag)]

    args = (Cursor(), deploy.attr.names([deploy.WORKLOAD]), 'DB.ANALYTICS.TASK', 'runtime-tag', now)
    if error:
        with pytest.raises(AssertionError if state == 'SUCCEEDED' else RuntimeError, match=error):
            deploy.verify_run(*args)
    else:
        assert deploy.verify_run(*args)['mismatch_count'] == 0
