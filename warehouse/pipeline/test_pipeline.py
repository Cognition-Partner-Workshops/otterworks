import csv
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import break_upstream
import load_daily
import sf
import checks
import fire_alert

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "observability/pipeline"))
from sfx_pipeline_exporter import Exporter
from prometheus_client import generate_latest


def test_connection_is_injectable():
    connector = Mock()
    sf.connect("load_break", "SFX_D1110_LOAD_WH", connector)
    args = connector.call_args.kwargs
    assert args["connection_name"] == "sfx_d1110"
    assert args["database"] == "SFX_D1110_AFTER"
    assert args["session_parameters"]["TIMEZONE"] == "UTC"
    assert json.loads(args["session_parameters"]["QUERY_TAG"]) == {
        "run": "sfx-d1110", "act": "operate", "step": "load_break"}
    with pytest.raises(ValueError):
        sf.connect("load", "OTHER_WH", connector)


def test_missing_feed_does_not_connect(monkeypatch):
    connector = Mock()
    monkeypatch.setattr(load_daily, "connect", connector)
    with pytest.raises(FileNotFoundError):
        load_daily.load(load_daily.date(1900, 1, 1))
    connector.assert_not_called()


def test_vendor_change_preserves_volume_but_shifts_columns(tmp_path, monkeypatch):
    landing = tmp_path / "landing"
    landing.mkdir()
    source = load_daily.ROOT / "landing" / "2026-11-09.csv"
    (landing / source.name).write_text(source.read_text())
    monkeypatch.setattr(break_upstream, "ROOT", tmp_path)
    day = break_upstream.generate()
    with (landing / f"{day}.csv").open() as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 49
    assert rows[0][8] == "DISCOUNT_CODE"
    assert all(row[7].startswith("$") for row in rows[1:])
    assert sum(len(row[8]) > 3 for row in rows[1:]) == 6
    assert all(len(row) == 12 for row in rows)


def test_empty_feed_is_still_header_only(tmp_path, monkeypatch):
    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "2026-11-09.csv").write_text(
        "USAGE_DAILY_ID,CUSTOMER_ID,ACCOUNT_NAME,INVOICE_NUMBER,USAGE_DATE,QUANTITY,"
        "UNIT_PRICE,AMOUNT,CURRENCY_CODE,CREATED_AT,IS_ACTIVE\n")
    monkeypatch.setattr(break_upstream, "ROOT", tmp_path)
    day = break_upstream.generate()
    assert len((landing / f"{day}.csv").read_text().splitlines()) == 1


def test_dbt_environment_uses_local_config(tmp_path):
    key = tmp_path / "dummy.p8"
    key.write_text("offline-dummy-key")
    config = tmp_path / "connections.toml"
    config.write_text('[sfx_d1110]\naccount="dummy"\nuser="dummy"\nrole="dummy"\n'
                      f'database="SFX_D1110_AFTER"\nprivate_key_file="{key}"\n')
    env = sf.dbt_env(config)
    assert env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] == "offline-dummy-key"
    assert json.loads(env["SFX_QUERY_TAG"])["step"] == "dbt_build"
    config.write_text(config.read_text().replace("SFX_D1110_AFTER", "OTHER"))
    with pytest.raises(ValueError):
        sf.dbt_env(config)


@pytest.mark.parametrize("results", [[], [(48, 0)]])
def test_load_replaces_only_its_source_and_builds(monkeypatch, results):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.description = [("rows_loaded",), ("errors_seen",)]
    cursor.fetchall.return_value = results
    monkeypatch.setattr(load_daily, "connect", Mock(return_value=connection))
    build = Mock()
    monkeypatch.setattr(load_daily, "build", build)
    load_daily.load(load_daily.GOOD_DATE)
    calls = cursor.execute.call_args_list
    assert calls[2].args == ("BEGIN",)
    assert calls[3].args == ("DELETE FROM RAW_BILLING.USAGE_DAILY WHERE _SRC_FILE=%s",
                            ("pipeline/2026-11-09.csv",))
    assert "ON_ERROR=ABORT_STATEMENT FORCE=TRUE" in calls[4].args[0]
    assert calls[5].args == ("COMMIT",)
    build.assert_called_once()


def test_reset_removes_only_break_file(tmp_path, monkeypatch):
    landing = tmp_path / "landing"
    landing.mkdir()
    good = landing / "2026-11-09.csv"
    broken = landing / "2026-11-10.csv"
    good.touch()
    broken.touch()
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(load_daily, "ROOT", tmp_path)
    monkeypatch.setattr(load_daily, "connect", Mock(return_value=connection))
    build = Mock()
    monkeypatch.setattr(load_daily, "build", build)
    load_daily.reset(load_daily.date(2026, 11, 10))
    assert good.exists() and not broken.exists()
    assert cursor.execute.call_args_list[0].args[1] == ("pipeline/2026-11-10.csv",)
    build.assert_called_once()


def test_copy_failure_does_not_claim_success_or_build(monkeypatch):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = [None, None, None, None, RuntimeError("offline copy failure"), None]
    monkeypatch.setattr(load_daily, "connect", Mock(return_value=connection))
    build = Mock()
    monkeypatch.setattr(load_daily, "build", build)
    with pytest.raises(RuntimeError, match="offline copy failure"):
        load_daily.load(load_daily.GOOD_DATE)
    build.assert_not_called()
    assert cursor.execute.call_args.args == ("ROLLBACK",)


@pytest.mark.parametrize("header", ["", "USAGE_DAILY_ID,CUSTOMER_ID\n"])
def test_missing_headers_fail_before_connect(tmp_path, monkeypatch, header):
    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "2026-11-09.csv").write_text(header)
    monkeypatch.setattr(load_daily, "ROOT", tmp_path)
    connector = Mock()
    monkeypatch.setattr(load_daily, "connect", connector)
    with pytest.raises(ValueError, match="missing required columns"):
        load_daily.load(load_daily.GOOD_DATE)
    connector.assert_not_called()


@pytest.mark.parametrize("schema,warehouse", [("OTHER", "SFX_D1110_LOAD_WH"),
                                              ("RAW_BILLING;DROP", "SFX_D1110_LOAD_WH"),
                                              ("RAW_BILLING", "OTHER_WH")])
def test_invalid_target(schema, warehouse):
    with pytest.raises(ValueError):
        load_daily.validate_target(schema, warehouse)


def test_header_only_reordered_feed_and_clone_target(tmp_path, monkeypatch, capsys):
    landing = tmp_path / "landing"
    landing.mkdir()
    header = ["DISCOUNT_CODE", *reversed(load_daily.REQUIRED)]
    path = landing / "2026-11-09.csv"
    path.write_text(",".join(header) + "\n")
    monkeypatch.setattr(load_daily, "ROOT", tmp_path)
    connection = MagicMock()
    connector = Mock(return_value=connection)
    monkeypatch.setattr(load_daily, "connect", connector)
    build = Mock()
    monkeypatch.setattr(load_daily, "build", build)
    load_daily.load(load_daily.GOOD_DATE, "backfill", "RAW_BILLING_SFX_D1110_BACKFILL",
                    "SFX_D1110_TRANSFORM_WH", True)
    connector.assert_called_once_with("backfill", "SFX_D1110_TRANSFORM_WH")
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    sql = cursor.execute.call_args_list[4].args[0]
    assert "COPY INTO RAW_BILLING_SFX_D1110_BACKFILL.USAGE_DAILY" in sql
    assert "TRY_TO_NUMBER($10),TRY_TO_NUMBER($9),TRY_TO_DATE($8)" in sql
    assert "TRY_TO_DECIMAL(REGEXP_REPLACE($5, '[^0-9.+-]', ''),12,2)" in sql
    assert "ignored extra columns: DISCOUNT_CODE" in capsys.readouterr().out
    build.assert_not_called()


def monitoring_fixture(broken=False):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    days = [("2026-11-10", 42, 42, 42), ("2026-11-09", 48, 0, 0)] if broken else [("2026-11-09", 48, 0, 0)]
    history = [("pipeline/2026-11-10.csv", "Partially loaded", 6, None),
               ("pipeline/2026-11-09.csv", "Loaded", 0, None)]
    files = [("landing_stage/pipeline/2026-11-09.csv",)]
    if broken:
        files.append(("landing_stage/pipeline/2026-11-10.csv",))
    cursor.fetchall.side_effect = [days, history, files]
    return Mock(return_value=connection)


@pytest.mark.parametrize("broken", [False, True])
def test_shared_checks_with_mocked_connector(broken):
    connector = monitoring_fixture(broken)
    result = checks.run_checks(connector=connector)
    connector.assert_called_once_with("monitor", "SFX_D1110_OPS_WH")
    assert all(c["firing"] == broken for c in result["checks"].values())
    assert result["load_errors"] == (6 if broken else 0)
    assert result["null_ratios"]["amount"] == (1 if broken else 0)


def test_empty_history_and_no_previous_day():
    result = checks.evaluate([], [], set(), checks.Thresholds())
    assert not any(c["firing"] for c in result["checks"].values())
    assert result["days"]["latest"] is None
    result = checks.evaluate([("2026-11-09", 48, 0, 0)], [], set(), checks.Thresholds())
    assert result["checks"]["row_count_drop"]["value"] == 0


def test_failed_status_without_errors_and_successful_replay():
    history = [("pipeline/2026-11-10.csv", "Load failed", 0, None)]
    files = {history[0][0]}
    result = checks.evaluate([], history, files, checks.Thresholds())
    assert result["checks"]["load_failure"]["firing"]
    history.insert(0, (history[0][0], "Loaded", 0, None))
    assert not checks.evaluate([], history, files, checks.Thresholds())["checks"]["load_failure"]["firing"]


def test_threshold_configuration():
    with pytest.raises(ValueError):
        checks.Thresholds(row_drop=-1)
    with pytest.raises(ValueError):
        checks.Thresholds(lookback_hours=337)
    result = checks.evaluate([("2026-11-10", 42, 1, 0), ("2026-11-09", 48, 0, 0)],
                             [], set(), checks.Thresholds(row_drop=.2, null_ratio=.1))
    assert not any(c["firing"] for c in result["checks"].values())


def test_payload_dry_run_and_all_green(capsys):
    result = checks.run_checks(connector=monitoring_fixture(True))
    body = fire_alert.payload(result, now="2026-11-10T00:00:00Z")
    assert len(body["alerts"]) == 3
    assert body["status"] == "firing"
    assert fire_alert.deliver(body, url="", secret="do-not-print") == 0
    output = capsys.readouterr().out
    assert "do-not-print" not in output
    assert json.loads(output) == body
    green = fire_alert.payload(checks.run_checks(connector=monitoring_fixture(False)))
    opener = Mock()
    assert fire_alert.deliver(green, url="https://example.invalid", opener=opener) == 0
    opener.assert_not_called()
    assert green["status"] == "resolved" and green["alerts"] == []


def test_webhook_success_failure_and_auth(capsys):
    body = fire_alert.payload(checks.run_checks(connector=monitoring_fixture(True)))
    response = MagicMock()
    response.__enter__.return_value.status = 200
    opener = Mock(return_value=response)
    assert fire_alert.deliver(body, "https://example.invalid", "offline-token", opener) == 0
    assert opener.call_args.args[0].get_header("Authorization") == "Bearer offline-token"
    opener.side_effect = fire_alert.URLError("not logged")
    assert fire_alert.deliver(body, "https://example.invalid", "offline-token", opener) == 1
    assert fire_alert.deliver(body, "https://example.invalid", "", opener) == 1
    assert "offline-token" not in str(capsys.readouterr())


def test_exporter_refresh_and_failure_with_mocked_connector():
    exporter = Exporter()
    def checker(limits):
        return checks.run_checks(limits, connector=monitoring_fixture(True))
    assert exporter.refresh(checks.Thresholds(), checker)
    metrics = generate_latest(exporter.registry).decode()
    assert 'sfx_pipeline_load_errors{model="stg_billing__usage_daily",run="sfx-d1110"} 6.0' in metrics
    assert 'check="null_spike"' in metrics
    assert not exporter.refresh(checks.Thresholds(), Mock(side_effect=RuntimeError("offline")))
    assert 'sfx_pipeline_last_scrape_success{model="stg_billing__usage_daily",run="sfx-d1110"} 0.0' in generate_latest(exporter.registry).decode()


def test_fixture_end_to_end_good_then_break(tmp_path, monkeypatch, capsys):
    class FixtureCursor:
        def __init__(self):
            self.days = {}
            self.files = {}
            self.result = []
            self.description = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            if sql.startswith("PUT"):
                self.day = "2026-11-10" if "2026-11-10.csv" in sql else "2026-11-09"
            elif sql.startswith("DELETE"):
                self.days.pop(Path(params[0]).stem, None)
            elif sql.startswith("COPY"):
                with (landing / f"{self.day}.csv").open() as handle:
                    records = list(csv.reader(handle))[1:]
                assert "ON_ERROR=ABORT_STATEMENT" in sql
                mapping = load_daily.header_columns(landing / f"{self.day}.csv")
                assert f"TRY_TO_TIMESTAMP_NTZ({mapping['CREATED_AT']})" in sql
                assert f"REGEXP_REPLACE({mapping['AMOUNT']}" in sql
                loaded = records
                errors = 0
                status = "Loaded"
                self.days[self.day] = (self.day, len(loaded),
                                       0, 0)
                self.files[f"pipeline/{self.day}.csv"] = (status, errors)
                self.description = [(name,) for name in ("rows_loaded", "errors_seen", "status")]
                self.result = [(len(loaded), errors, status)]
            elif "SELECT s.USAGE_DATE" in sql:
                self.result = sorted(self.days.values(), reverse=True)[:2]
            elif "INFORMATION_SCHEMA.COPY_HISTORY" in sql:
                self.result = [(name, status, errors, None)
                               for name, (status, errors) in self.files.items()]
            elif sql.startswith("LIST"):
                self.result = [(name,) for name in self.files]
            return self

        def fetchall(self):
            return self.result

    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "2026-11-09.csv").write_text(
        (load_daily.ROOT / "landing/2026-11-09.csv").read_text())
    cursor = FixtureCursor()
    connection = MagicMock()
    connection.__enter__.return_value.cursor.return_value = cursor
    connector = Mock(return_value=connection)
    monkeypatch.setattr(load_daily, "ROOT", tmp_path)
    monkeypatch.setattr(break_upstream, "ROOT", tmp_path)
    monkeypatch.setattr(load_daily, "connect", connector)
    monkeypatch.setattr(checks, "connect", connector)
    monkeypatch.setattr(load_daily, "dbt_env", lambda: {})
    dbt = Mock()
    monkeypatch.setattr(load_daily.subprocess, "run", dbt)
    monkeypatch.delenv("DEVIN_PIPELINE_WEBHOOK_URL", raising=False)
    for day, expected_firing in (("2026-11-09", False), ("2026-11-10", True)):
        if expected_firing:
            break_upstream.generate()
        monkeypatch.setattr(sys, "argv", ["load_daily.py", "--date", day])
        load_daily.main()
        capsys.readouterr()
        result = checks.run_checks()
        assert not any(check["firing"] for check in result["checks"].values())
        monkeypatch.setattr(sys, "argv", ["fire_alert.py"])
        assert fire_alert.main() == 0
        body = json.loads(capsys.readouterr().out)
        assert body["status"] == "resolved"
        assert body["alerts"] == []
    assert result["rows"] == {"latest": 48, "previous": 48}
    assert result["load_errors"] == 0
    assert dbt.call_count == 2
    assert all("source:billing.USAGE_DAILY+" in call.args[0] for call in dbt.call_args_list)
