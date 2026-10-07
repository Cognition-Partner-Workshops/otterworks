import configparser
import os
from pathlib import Path

import pytest

import legacy_cron

ETL_DIR = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ETL_DIR / "tests" / "golden"
# etl/crontab as it was before the Airflow cutover (etl/RUNBOOK.md §5): the schedule contract.
PRE_CUTOVER = ETL_DIR / "legacy-cron" / "crontab.pre-cutover"


@pytest.fixture
def committed_jobs():
    return legacy_cron.parse_crontab(PRE_CUTOVER.read_text())


def test_crontab_keeps_only_unmodified_pre_cutover_lines():
    pre = PRE_CUTOVER.read_text().splitlines()
    current = (ETL_DIR / "crontab").read_text().splitlines()
    assert current[:2] == pre[:2]
    assert [line for line in current if line in pre] == current
    legacy_cron.parse_crontab("\n".join(current))


def test_committed_crontab_parses_to_five_unmodified_lines(committed_jobs):
    assert [j.schedule for j in committed_jobs] == [
        "0 2 * * *",
        "0 3 * * 0",
        "0 4 * * 0",
        "30 2 * * *",
        "0 5 * * *",
    ]
    raw = PRE_CUTOVER.read_text()
    for job in committed_jobs:
        assert "%s %s" % (job.schedule, job.command) in raw
        assert job.command.startswith("/opt/etl/run.sh ")


def test_every_committed_log_target_is_linked(committed_jobs):
    assert legacy_cron.log_targets(committed_jobs) == [
        "/var/log/etl/analytics.log",
        "/var/log/etl/audit.log",
        "/var/log/etl/search.log",
        "/var/log/etl/storage.log",
        "/var/log/etl/activity.log",
    ]


def test_parse_skips_comments_blanks_and_env_lines():
    jobs = legacy_cron.parse_crontab(
        "# comment\n\nMAILTO=data-team\n@daily /opt/etl/run.sh a.py\n"
        "*/5 * * * * /opt/etl/run.sh b.py > /var/log/etl/b.log 2>&1\n"
    )
    assert jobs == [
        legacy_cron.Job("@daily", "/opt/etl/run.sh a.py"),
        legacy_cron.Job(
            "*/5 * * * *", "/opt/etl/run.sh b.py > /var/log/etl/b.log 2>&1"
        ),
    ]


def test_parse_rejects_malformed_line():
    with pytest.raises(ValueError):
        legacy_cron.parse_crontab("0 2 * *\n")


def test_log_targets_ignore_paths_outside_log_dir():
    jobs = [legacy_cron.Job("* * * * *", "x >> /tmp/x.log 2>&1; y >/var/log/etl/y.log")]
    assert legacy_cron.log_targets(jobs) == ["/var/log/etl/y.log"]


def test_link_logs_to_stdout_replaces_existing_files(tmp_path):
    existing = tmp_path / "analytics.log"
    existing.write_text("old")
    fresh = tmp_path / "nested" / "audit.log"
    legacy_cron.link_logs_to_stdout([str(existing), str(fresh)])
    for path in (existing, fresh):
        assert path.is_symlink()
        assert os.readlink(path) == "/dev/stdout"


def test_job_for_script_finds_only_present_lines(committed_jobs):
    job = legacy_cron.job_for_script(committed_jobs, "storage_cleanup_daily.py")
    assert job.schedule == "30 2 * * *"
    remaining = [
        j for j in committed_jobs if "storage_cleanup_daily.py" not in j.command
    ]
    assert legacy_cron.job_for_script(remaining, "storage_cleanup_daily.py") is None
    assert legacy_cron.job_for_script(committed_jobs, "daily.py") is None


def test_run_refuses_a_cut_over_script(tmp_path, monkeypatch):
    crontab = tmp_path / "crontab"
    crontab.write_text("0 2 * * * /opt/etl/run.sh analytics_daily.py\n")
    monkeypatch.setattr(legacy_cron, "CRONTAB", str(crontab))
    monkeypatch.setattr(legacy_cron, "render_config", lambda: None)
    assert (
        legacy_cron.run("user_activity_daily.py") == legacy_cron.NOT_SCHEDULED_EXIT_CODE
    )


LOCAL_SERVICES = {
    "LEGACY_CRON_DOCUMENT_SERVICE_URL": "http://docs:1",
    "LEGACY_CRON_FILE_SERVICE_URL": "http://files:2",
}


def _render(tmp_path):
    target = tmp_path / "config.ini"
    legacy_cron.render_config(str(target), str(GOLDEN_DIR), env=LOCAL_SERVICES)
    rendered = configparser.ConfigParser()
    rendered.read(target)
    return target, rendered


def test_render_config_uses_harness_renderer_with_local_values(tmp_path):
    target, rendered = _render(tmp_path)
    assert oct(target.stat().st_mode & 0o777) == "0o600"
    assert rendered["services"]["document_service_url"] == "http://docs:1"
    assert rendered["services"]["file_service_url"] == "http://files:2"
    assert rendered["aws"]["access_key"] == "test"
    assert rendered["database"]["database"] == "otterworks_etl_golden"
    assert sorted(rendered.sections()) == ["aws", "database", "s3", "services"]


def test_render_config_requires_service_urls(tmp_path):
    with pytest.raises(KeyError):
        legacy_cron.render_config(str(tmp_path / "c.ini"), str(GOLDEN_DIR), env={})


def test_rendered_credentials_and_hosts_are_not_the_committed_ones(tmp_path):
    _, rendered = _render(tmp_path)
    committed = configparser.ConfigParser()
    committed.read(ETL_DIR / "config.ini")
    for section, key in [
        ("aws", "access_key"),
        ("aws", "secret_key"),
        ("database", "host"),
        ("database", "user"),
        ("database", "password"),
        ("database", "database"),
        ("services", "document_service_url"),
        ("services", "file_service_url"),
        ("services", "meilisearch_url"),
        ("services", "meilisearch_api_key"),
    ]:
        assert rendered[section][key] != committed[section][key], (section, key)
