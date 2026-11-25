"""Check that the local Compose stack requires and shares a PostgreSQL password."""

import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[2]
INFRA = ("docker-compose.infra.yml",)
STACK = (*INFRA, "docker-compose.yml")


def compose_config(files, password):
    command = ["docker", "compose", "--env-file", os.devnull]
    for file in files:
        command.extend(("-f", file))
    env = os.environ.copy()
    env.pop("DB_PASSWORD", None)
    if password is not None:
        env["DB_PASSWORD"] = password
    return subprocess.run(
        [*command, "config", "--format", "json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("files", [INFRA, STACK], ids=["infra", "stack"])
@pytest.mark.parametrize("password", [None, ""], ids=["unset", "empty"])
def test_compose_requires_db_password(files, password):
    result = compose_config(files, password)
    assert result.returncode != 0, "Compose must reject missing database credentials"
    assert "DB_PASSWORD" in result.stderr, "Compose must identify the missing variable"


def test_compose_uses_the_supplied_db_password_for_all_clients():
    password = secrets.token_hex(32)
    result = compose_config(STACK, password)
    assert result.returncode == 0, "Compose must accept a supplied database password"
    services = json.loads(result.stdout)["services"]
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"] == password

    for service, config in services.items():
        env = config.get("environment", {})
        for key in ("POSTGRES_PASSWORD", "SPRING_DATASOURCE_PASSWORD", "DATABASE_PASSWORD", "DB_PASSWORD"):
            if key in env:
                assert env[key] == password, f"{service} must use the supplied {key}"

    for service, key in (
        ("admin-service", "DATABASE_URL"),
        ("document-service", "DOC_SVC_DATABASE_URL"),
    ):
        url = urlsplit(services[service]["environment"][key])
        assert url.password == password, f"{service} must use the supplied URL credential"
        assert (url.hostname, url.port, url.username, url.path) == (
            "postgres",
            5432,
            "otterworks",
            "/otterworks",
        )
