from __future__ import annotations

import ast

from tests.conftest import DAGS_FOLDER

DAG_ID = "otterworks_analytics_etl"
DAG_FILE = DAGS_FOLDER / f"{DAG_ID}.py"


def _downstream(dag, task_id):
    return set(dag.get_task(task_id).downstream_task_ids)


def test_task_graph(dagbag):
    dag = dagbag.dags[DAG_ID]
    assert dag.schedule_interval == "0 2 * * *"
    assert _downstream(dag, "extract_from_sqs") == {"transform_events"}
    assert _downstream(dag, "extract_from_dynamodb") == {"transform_events"}
    assert set(dag.get_task("transform_events").upstream_task_ids) == {
        "extract_from_sqs",
        "extract_from_dynamodb",
    }
    assert _downstream(dag, "transform_events") == {
        "load_to_data_lake",
        "update_postgres_aggregates",
        "generate_report",
    }
    assert set(dag.get_task("generate_report").upstream_task_ids) == {
        "transform_events",
        "load_to_data_lake",
        "update_postgres_aggregates",
    }
    assert _downstream(dag, "generate_report") == {"cleanup_staging"}
    assert dag.get_task("cleanup_staging").trigger_rule == "none_failed"


def test_uses_provider_hooks_only():
    tree = ast.parse(DAG_FILE.read_text())
    imported = {
        alias.name.split(".")[0] if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not {m for m in imported if m.split(".")[0] in {"boto3", "botocore", "psycopg2"}}
    for hook in ("SqsHook", "DynamoDBHook", "S3Hook", "PostgresHook"):
        assert hook in DAG_FILE.read_text()


def test_no_hardcoded_queue_url():
    assert "sqs.us-east-1.amazonaws.com" not in DAG_FILE.read_text()
