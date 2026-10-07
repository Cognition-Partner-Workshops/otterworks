"""Static checks on the DAG parity runner's committed inputs (no infra, no Airflow needed)."""

import json
import re
from pathlib import Path

import pytest

from harness import airflow_container, differences, parity, scenario, settings
from harness.differences import ABSENT

DECIDED_FLAGS = ("audit_archive_delete_enabled", "storage_cleanup_normalize_keys")
TOY_DAGS = (airflow_container.TOY_DAG_FOLDER / "parity_toy_dags.py").read_text()


def golden_checks(script, name):
    scn = next(s for s in scenario.discover(script, name))
    files = {p.name: json.loads(p.read_text()) for p in scn.golden_dir.glob("*.json")}
    return differences.checks(files)


def test_every_registered_dag_is_a_known_toy_or_image_dag():
    scripts, controls = parity.load_registry()
    assert set(scripts) <= set(settings.SCRIPTS)
    for entry in [*scripts.values(), *controls.values()]:
        if entry.dag_folder == "toy":
            assert entry.dag_id.startswith(("parity_passthrough__", "parity_wrong__"))
            assert entry.dag_id.split("__", 1)[1] == entry.script
            assert entry.variants is False, "toy DAGs run legacy and ignore Variables"
        else:
            assert (settings.ETL_DIR / "airflow" / "dags").is_dir()
    assert '"parity_passthrough__%s" % _script' in TOY_DAGS
    assert set(controls) == set(re.findall(r'"(parity_wrong__\w+)"', TOY_DAGS))


@pytest.mark.parametrize("script", settings.SCRIPTS)
def test_default_differences_are_reviewed_against_the_golden(script):
    """The pass-through runs legacy, so it accepts nothing. A ported DAG lists only what it
    changes, each `before` being the committed golden. The decided flags default to false,
    which is the legacy goldens, so they add no default difference."""
    scripts, _ = parity.load_registry()
    accepted = differences.load(script).default
    if scripts[script].dag_folder == "toy":
        assert accepted == {}
    for name, entries in accepted.items():
        golden = golden_checks(script, name)
        for acc in entries:
            assert differences.canon(golden.get(acc.check, ABSENT)) == differences.canon(
                acc.before
            ), acc.check


def test_decided_flags_default_false_and_each_has_a_flag_on_variant():
    defaults = airflow_container.default_variables()
    assert {flag: defaults[flag] for flag in DECIDED_FLAGS} == dict.fromkeys(
        DECIDED_FLAGS, "false"
    )
    flipped = {
        flag
        for script in settings.SCRIPTS
        for v in differences.load(script).variants
        for flag, value in v.variables.items()
        if value is True
    }
    assert flipped == set(DECIDED_FLAGS)


VARIANTS = [
    (script, v)
    for script in settings.SCRIPTS
    for v in differences.load(script).variants
]


@pytest.mark.parametrize(
    "script, variant", VARIANTS, ids=lambda x: getattr(x, "name", x)
)
def test_variant_before_values_are_the_committed_golden(script, variant):
    golden = golden_checks(script, variant.scenario)
    defaults = airflow_container.default_variables()
    for key, value in variant.variables.items():
        assert key in defaults
        assert airflow_container.variable_value(value) != defaults[key], (
            "override is a no-op"
        )
    assert variant.accepted, "a flag-on variant documents what it changes"
    for acc in variant.accepted:
        assert golden.get(acc.check, ABSENT) == acc.before or (
            differences.canon(golden.get(acc.check, ABSENT))
            == differences.canon(acc.before)
        ), acc.check


def test_variant_case_reuses_the_base_scenario_seed():
    entry = parity.resolve_dag("audit_archive_weekly", None)
    default_cases = parity.cases("audit_archive_weekly", entry, None, None)
    names = {s.name for s in scenario.discover("audit_archive_weekly")}
    assert all(c.variables == {} for c in default_cases if c.scn.name in names)
    assert {c.scn.name for c in default_cases} - names == {
        v.name for v in differences.load("audit_archive_weekly").variants
    }, "a ported DAG runs its flag-on variants with the default cases"
    (case,) = parity.cases("audit_archive_weekly", entry, None, "smoke_delete_enabled")
    base = next(iter(scenario.discover("audit_archive_weekly", "smoke")))
    assert case.scn.seed == base.seed and case.scn.golden_dir == base.golden_dir
    assert case.scn.name == "smoke_delete_enabled"
    assert case.variables == {"audit_archive_delete_enabled": True}
    assert "audit_archive_delete_enabled=true" in case.label


def test_run_environment_points_every_connection_at_the_harness_stack():
    env = airflow_container.run_environment(
        "http://127.0.0.1:9999",
        {"audit_archive_delete_enabled": True},
        Path("/x/config.ini"),
        "2026-03-15T03:00:00Z",
        "legacy:tag",
    )
    conns = {
        k[len("AIRFLOW_CONN_") :].lower(): json.loads(v)
        for k, v in env.items()
        if k.startswith("AIRFLOW_CONN_")
    }
    assert set(conns) == airflow_container.connection_ids()
    assert conns["aws_default"]["extra"]["endpoint_url"] == settings.LOCALSTACK_URL
    assert conns["otterworks_postgres"]["schema"] == settings.PG_DB
    assert (
        conns["otterworks_document_service"]["host"]
        == "http://127.0.0.1:9999/document-service"
    )
    assert env["AIRFLOW_VAR_AUDIT_ARCHIVE_DELETE_ENABLED"] == "true"
    assert env["AIRFLOW_VAR_STORAGE_CLEANUP_NORMALIZE_KEYS"] == "false"
    assert env["PARITY_CONFIG_PATH"] == "/x/config.ini"
    for value in env.values():
        assert "amazonaws.com" not in value


def test_unknown_variable_override_is_rejected():
    with pytest.raises(airflow_container.AirflowError, match="not defined"):
        airflow_container.run_environment(
            "http://x", {"audit_archive_delete_enabld": True}, Path("/c"), "t", "i"
        )


def test_toy_dags_reuse_the_harness_legacy_run():
    for call in (
        "runner.legacy_command(",
        "runner.legacy_environment(",
        "runner.legacy_mounts(",
    ):
        assert call in TOY_DAGS
    assert "DockerOperator(" in TOY_DAGS


def test_override_check_uses_what_the_dag_read():
    output = "\n".join(
        [
            "noise",
            'PARITY_VARIABLE_READ {"key": "data_lake_bucket", "value": "otterworks-data-lake"}',
            '[2026] x PARITY_VARIABLE_READ {"key": "audit_archive_delete_enabled", "value": "true"}',
        ]
    )
    read = airflow_container.variables_read(output)
    assert read == {
        "data_lake_bucket": ["otterworks-data-lake"],
        "audit_archive_delete_enabled": ["true"],
    }
    entry = parity.resolve_dag("audit_archive_weekly", None)
    (case,) = parity.cases("audit_archive_weekly", entry, None, "smoke_delete_enabled")
    (row,) = parity.override_rows(case, read)
    assert (row.result, row.before, row.after) == (
        differences.IDENTICAL,
        "true",
        "true",
    )

    (row,) = parity.override_rows(case, {})
    assert row.result == differences.FAILED and row.after is ABSENT
    assert "never read" in row.reason
    (row,) = parity.override_rows(
        case, {"audit_archive_delete_enabled": ["true", "false"]}
    )
    assert row.result == differences.FAILED and "different value" in row.reason


def test_secrets_backend_marker_matches_the_runner():
    backend = (airflow_container.PARITY_DIR / "parity_secrets.py").read_text()
    assert 'MARKER = "%s"' % airflow_container.VARIABLE_MARKER in backend


def test_service_connections_keep_the_stub_route_prefix():
    conns = airflow_container.connections("http://stub:9999")
    assert conns["otterworks_document_service"] == {
        "conn_type": "http",
        "host": "http://stub:9999/document-service",
    }
    assert "://" not in conns["otterworks_meilisearch"]["host"]


def test_config_overrides_reach_the_dag_inputs():
    for script in settings.SCRIPTS:
        for scn in scenario.discover(script):
            airflow_container.config_inputs(scn.config_overrides)
    env = airflow_container.run_environment(
        "http://x",
        {},
        Path("/c"),
        "t",
        "i",
        {
            "database": {"password": "wrong-password"},
            "s3": {"quarantine_bucket": "q-missing"},
        },
    )
    assert (
        json.loads(env["AIRFLOW_CONN_OTTERWORKS_POSTGRES"])["password"]
        == "wrong-password"
    )
    assert env["AIRFLOW_VAR_QUARANTINE_BUCKET"] == "q-missing"
    with pytest.raises(airflow_container.AirflowError, match="no Airflow"):
        airflow_container.config_inputs(
            {"services": {"meilisearch_url": "http://elsewhere"}}
        )
    with pytest.raises(airflow_container.AirflowError, match="removed"):
        airflow_container.config_inputs({"database": None})
