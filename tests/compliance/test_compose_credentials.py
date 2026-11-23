"""The local compose stack must not carry its Postgres password in the repo.

Compose reads ${POSTGRES_PASSWORD} from the untracked .env that
scripts/dev-env.sh writes with a per-machine random value.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = [ROOT / "docker-compose.infra.yml", ROOT / "docker-compose.yml"]
REQUIRED_REF = re.compile(r"^\$\{POSTGRES_PASSWORD:\?[^}]*\}$")
URL_PASSWORD = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^:/\s@]+:(\$\{[^}]*\}|[^@\s]+)@")
PASSWORD_KEY = re.compile(r"^\s*(POSTGRES_PASSWORD|DB_PASSWORD|DATABASE_PASSWORD|SPRING_DATASOURCE_PASSWORD):\s*(.+?)\s*$")


def _lines():
    for path in COMPOSE_FILES:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            yield f"{path.name}:{number}", line


def test_postgres_urls_take_the_password_from_the_environment():
    urls = [(where, m.group(1)) for where, line in _lines() for m in URL_PASSWORD.finditer(line)]
    assert urls, "expected Postgres connection URLs in the compose files"
    literal = [(where, pw) for where, pw in urls if not REQUIRED_REF.match(pw)]
    assert literal == []


def test_password_keys_take_the_password_from_the_environment():
    keys = [(where, m.group(2)) for where, line in _lines() if (m := PASSWORD_KEY.match(line))]
    assert keys, "expected Postgres password keys in the compose files"
    literal = [(where, value) for where, value in keys if not REQUIRED_REF.match(value)]
    assert literal == []


def test_env_file_is_not_tracked():
    result = subprocess.run(["git", "check-ignore", "-q", ".env"], check=False, cwd=ROOT)
    assert result.returncode == 0


def _run_dev_env(workdir: Path) -> str:
    (workdir / "scripts").mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/dev-env.sh", workdir / "scripts/dev-env.sh")
    subprocess.run(["bash", "scripts/dev-env.sh"], cwd=workdir, check=True, capture_output=True)
    env = (workdir / ".env").read_text()
    assert oct((workdir / ".env").stat().st_mode & 0o777) == "0o600"
    return re.search(r"^POSTGRES_PASSWORD=(.*)$", env, re.MULTILINE).group(1)


def test_dev_env_writes_a_random_password_once(tmp_path):
    first, second = tmp_path / "a-machine", tmp_path / "b-machine"
    first.mkdir()
    second.mkdir()
    password = _run_dev_env(first)
    assert re.fullmatch(r"[0-9a-f]{48}", password)
    assert _run_dev_env(first) == password
    assert _run_dev_env(second) != password


def _compose_config(env_file: Path):
    cmd = ["docker", "compose", "--env-file", str(env_file)]
    for path in COMPOSE_FILES:
        cmd += ["-f", str(path)]
    return subprocess.run(cmd + ["config", "--format", "json"], check=False, cwd=ROOT, capture_output=True, text=True)


@pytest.mark.skipif(
    shutil.which("docker") is None
    or subprocess.run(["docker", "compose", "version"], check=False, capture_output=True).returncode != 0,
    reason="docker compose not available",
)
def test_compose_resolves_one_password_and_refuses_to_run_without_it(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_PASSWORD=per-machine-test-value\n")
    config = _compose_config(env_file)
    assert config.returncode == 0, config.stderr
    services = json.loads(config.stdout)["services"]
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"] == "per-machine-test-value"
    assert services["document-service"]["environment"]["DOC_SVC_DATABASE_URL"] == (
        "postgresql+asyncpg://otterworks:per-machine-test-value@postgres:5432/otterworks"
    )

    env_file.write_text("")
    missing = _compose_config(env_file)
    assert missing.returncode != 0
    assert "run make dev-env" in missing.stderr
