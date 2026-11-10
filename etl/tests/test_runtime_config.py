import ast
import json
import os
from pathlib import Path
import secrets
import sys
from unittest.mock import Mock

import pytest

ETL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL / "scripts"))

from runtime_config import load_config, required_secret
import run_job
from run_job import JOBS, SECRET_NAMES, populate_secrets


def test_secret_from_environment(monkeypatch):
    value = secrets.token_urlsafe(24)
    monkeypatch.setenv("ETL_DB_PASSWORD", value)
    assert required_secret("ETL_DB_PASSWORD") == value


@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_secret_is_clear(monkeypatch, value):
    monkeypatch.delenv("ETL_DB_PASSWORD", raising=False)
    if value is not None:
        monkeypatch.setenv("ETL_DB_PASSWORD", value)
    with pytest.raises(RuntimeError, match="Required ETL secret ETL_DB_PASSWORD is missing or empty"):
        required_secret("ETL_DB_PASSWORD")


def test_config_has_no_credential_keys(monkeypatch):
    monkeypatch.setenv("ETL_CONFIG_PATH", str(ETL / "config.ini"))
    config = load_config()
    forbidden = {"access_key", "secret_key", "password", "meilisearch_api_key"}
    assert all(not forbidden.intersection(config[section]) for section in config.sections())
    assert config.get("aws", "region") == "us-east-1"


def test_config_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("ETL_CONFIG_PATH", str(tmp_path / "absent.ini"))
    with pytest.raises(RuntimeError, match="ETL configuration not found"):
        load_config()


def test_secrets_manager_populates_only_allowed_environment(monkeypatch):
    values = {name: secrets.token_urlsafe(24) for name in SECRET_NAMES}
    values["UNRELATED"] = "ignored"
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": json.dumps(values)}
    monkeypatch.setenv("ETL_SECRET_ID", "custom/runtime")
    for name in SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("UNRELATED", raising=False)
    populate_secrets(client)
    client.get_secret_value.assert_called_once_with(SecretId="custom/runtime")
    assert all(os.environ[name] == values[name] for name in SECRET_NAMES)
    assert "UNRELATED" not in os.environ


@pytest.mark.parametrize("payload", [None, "not-json", "[]", "{}", '{"ETL_DB_PASSWORD": ""}'])
def test_invalid_secret_fails_without_exposing_values(monkeypatch, payload):
    client = Mock()
    client.get_secret_value.return_value = {} if payload is None else {"SecretString": payload}
    for name in SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="ETL runtime secret"):
        populate_secrets(client)
    assert all(name not in os.environ for name in SECRET_NAMES)


def test_secrets_manager_failure_propagates():
    client = Mock()
    client.get_secret_value.side_effect = RuntimeError("AccessDenied")
    with pytest.raises(RuntimeError, match="AccessDenied"):
        populate_secrets(client)


def test_runner_fetches_secret_before_running_job(monkeypatch):
    values = {name: secrets.token_urlsafe(24) for name in SECRET_NAMES}
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": json.dumps(values)}
    factory = Mock(return_value=client)
    run_path = Mock()
    monkeypatch.setattr(run_job.boto3, "client", factory)
    monkeypatch.setattr(run_job.runpy, "run_path", run_path)
    monkeypatch.setattr(sys, "argv", ["run_job.py", "analytics_daily.py"])
    monkeypatch.setenv("ETL_CONFIG_PATH", str(ETL / "config.ini"))
    monkeypatch.delenv("ETL_SECRET_ID", raising=False)
    for name in SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    run_job.main()
    factory.assert_called_once_with("secretsmanager", region_name="us-east-1")
    client.get_secret_value.assert_called_once_with(SecretId="otterworks/etl/runtime")
    run_path.assert_called_once_with(str(ETL / "scripts" / "analytics_daily.py"), run_name="__main__")
    assert all(os.environ[name] == values[name] for name in SECRET_NAMES)


@pytest.mark.parametrize("job", JOBS)
def test_every_job_uses_shared_config_and_default_aws_chain(job):
    tree = ast.parse((ETL / "scripts" / job).read_text())
    assert any(isinstance(node, ast.ImportFrom) and node.module == "runtime_config" for node in ast.walk(tree))
    forbidden = {"aws_access_key_id", "aws_secret_access_key"}
    assert not any(isinstance(node, ast.keyword) and node.arg in forbidden for node in ast.walk(tree))
