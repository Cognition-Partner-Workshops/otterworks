import configparser
import re

from harness import config_ini, settings

CONFIG_READ = re.compile(r'config\.get(?:int)?\("([a-z_]+)", "([a-z_]+)"\)')


def rendered(overrides=None):
    parser = configparser.ConfigParser()
    parser.read_string(config_ini.render("http://127.0.0.1:9", overrides))
    return parser


def test_has_every_option_the_scripts_read():
    parser = rendered()
    # Retired scripts (etl/RUNBOOK.md section 9) are skipped: nothing reads their options.
    present = [
        path
        for path in (settings.ETL_DIR / "scripts" / ("%s.py" % s) for s in settings.SCRIPTS)
        if path.is_file()
    ]
    for path in present:
        script, source = path.stem, path.read_text()
        for section, option in CONFIG_READ.findall(source):
            assert parser.has_option(section, option), (script, section, option)


def test_committed_config_ini_is_retired():
    # The legacy runner and legacy-etl-cron mount only this renderer's output.
    assert not (settings.ETL_DIR / "config.ini").exists()


def test_only_local_endpoints():
    parser = rendered()
    assert parser.get("database", "host") in ("localhost", "127.0.0.1")
    for option in ("document_service_url", "file_service_url", "meilisearch_url"):
        assert re.match(
            r"^http://(localhost|127\.0\.0\.1):\d+", parser.get("services", option)
        )


def test_overrides_set_and_remove():
    parser = rendered(
        {"s3": {"archive_bucket": "other", "analytics_prefix": None}, "services": None}
    )
    assert parser.get("s3", "archive_bucket") == "other"
    assert not parser.has_option("s3", "analytics_prefix")
    assert not parser.has_section("services")
