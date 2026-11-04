import sys
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
