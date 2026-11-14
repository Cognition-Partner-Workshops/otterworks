"""Regression tests for ETL-142: no committed credentials, secrets read from the environment."""

import configparser
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

import etl_config

ETL_DIR = Path(__file__).resolve().parents[1]

SECRET_OPTIONS = {
    ("aws", "access_key"),
    ("aws", "secret_key"),
    ("database", "password"),
    ("services", "meilisearch_api_key"),
}

SAMPLE_INI = """
[aws]
access_key =
secret_key =
region = eu-west-1

[database]
host = db.from-file
port = 5432
database = otterworks_analytics
user = etl_user
password = from-file

[services]
document_service_url = http://document-service:8083
file_service_url = http://file-service:8082
meilisearch_url = http://meilisearch:7700
meilisearch_api_key =

[s3]
data_lake_bucket = lake
file_storage_bucket = files
quarantine_bucket = quarantine
archive_bucket = archive
analytics_prefix = analytics/daily
"""


def write_ini(test, text):
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    path = Path(tmp.name) / "config.ini"
    path.write_text(text)
    return path


class Halt(BaseException):
    """Raised by stubbed clients so a script stops at its first external call.

    Derives from BaseException so the scripts' ``except Exception`` blocks do not swallow it.
    """


class CommittedConfigTest(unittest.TestCase):
    def test_real_config_is_not_committed(self):
        if shutil.which("git") is None:
            self.skipTest("git not available")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "etl/config.ini"],
            cwd=ETL_DIR.parent, capture_output=True, check=False,
        )
        self.assertNotEqual(tracked.returncode, 0, "etl/config.ini must not be tracked")
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "etl/config.ini"], cwd=ETL_DIR.parent, check=False,
        )
        self.assertEqual(ignored.returncode, 0, "etl/config.ini must be git-ignored")

    def test_example_config_holds_no_secret_values(self):
        parser = configparser.ConfigParser()
        self.assertTrue(parser.read(ETL_DIR / "config.ini.example"))
        for section, option in SECRET_OPTIONS:
            self.assertEqual(parser.get(section, option).strip(), "", f"[{section}] {option} must be blank")


class LoaderTest(unittest.TestCase):
    def setUp(self):
        self.ini = write_ini(self, SAMPLE_INI)

    def test_env_overrides_config_file(self):
        cfg = etl_config.load_config(str(self.ini), {"ETL_DB_PASSWORD": "from-env", "ETL_DATABASE_HOST": "db.from-env"})
        self.assertEqual(cfg.get("database", "password"), "from-env")
        self.assertEqual(cfg.get("database", "host"), "db.from-env")
        self.assertEqual(cfg.getint("database", "port"), 5432)

    def test_config_file_used_when_env_unset(self):
        cfg = etl_config.load_config(str(self.ini), {})
        self.assertEqual(cfg.get("database", "password"), "from-file")
        self.assertEqual(cfg.get("aws", "region"), "eu-west-1")

    def test_config_path_from_env(self):
        cfg = etl_config.load_config(environ={"ETL_CONFIG_PATH": str(self.ini)})
        self.assertEqual(cfg.get("s3", "data_lake_bucket"), "lake")

    def test_missing_secret_fails_loudly(self):
        cfg = etl_config.load_config(str(ETL_DIR / "config.ini.example"), {})
        with self.assertRaises(etl_config.MissingSettingError) as ctx:
            cfg.get("database", "password")
        self.assertIn("ETL_DB_PASSWORD", str(ctx.exception))

    def test_optional_aws_keys_fall_back_to_default_chain(self):
        cfg = etl_config.load_config(str(self.ini), {})
        self.assertIsNone(cfg.get("aws", "access_key", required=False))
        self.assertIsNone(cfg.get("aws", "secret_key", required=False))

    def test_standard_aws_and_meili_env_names(self):
        env = {"AWS_ACCESS_KEY_ID": "AKIDENV", "AWS_SECRET_ACCESS_KEY": "secret-env",
               "AWS_REGION": "us-west-2", "MEILISEARCH_API_KEY": "meili-env"}
        cfg = etl_config.load_config(str(self.ini), env)
        self.assertEqual(cfg.get("aws", "access_key"), "AKIDENV")
        self.assertEqual(cfg.get("aws", "secret_key"), "secret-env")
        self.assertEqual(cfg.get("aws", "region"), "us-west-2")
        self.assertEqual(cfg.get("services", "meilisearch_api_key"), "meili-env")


class ScriptsReadEnvTest(unittest.TestCase):
    """Run each script's main() with stubbed clients and check the credentials they receive."""

    ENV: ClassVar[dict] = {
        "AWS_ACCESS_KEY_ID": "AKIDENV",
        "AWS_SECRET_ACCESS_KEY": "aws-secret-env",
        "ETL_DB_PASSWORD": "db-secret-env",
        "MEILISEARCH_API_KEY": "meili-secret-env",
    }

    def setUp(self):
        self.ini = write_ini(self, SAMPLE_INI.replace("password = from-file", "password ="))
        self.calls = []

        def record(kind):
            def fn(*args, **kwargs):
                self.calls.append((kind, args, kwargs))
                raise Halt()
            return fn

        stubs = {
            "boto3": types.SimpleNamespace(client=record("boto3"), resource=record("boto3")),
            "psycopg2": types.SimpleNamespace(connect=record("psycopg2")),
            "pandas": types.ModuleType("pandas"),
            "requests": types.SimpleNamespace(delete=record("requests"), get=record("requests"),
                                              post=record("requests"), put=record("requests")),
        }
        env = dict(self.ENV, ETL_CONFIG_PATH=str(self.ini))
        patches = [mock.patch.dict(sys.modules, stubs), mock.patch.dict(os.environ, env)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_script(self, name):
        sys.modules.pop(name, None)
        module = importlib.import_module(name)
        with mock.patch("builtins.print"), self.assertRaises(Halt):
            module.main()
        return self.calls[0]

    def assert_aws_creds_from_env(self, call):
        kind, _, kwargs = call
        self.assertEqual(kind, "boto3")
        self.assertEqual(kwargs["aws_access_key_id"], "AKIDENV")
        self.assertEqual(kwargs["aws_secret_access_key"], "aws-secret-env")
        self.assertEqual(kwargs["region_name"], "eu-west-1")

    def test_analytics_daily(self):
        self.assert_aws_creds_from_env(self.run_script("analytics_daily"))

    def test_audit_archive_weekly(self):
        self.assert_aws_creds_from_env(self.run_script("audit_archive_weekly"))

    def test_storage_cleanup_daily(self):
        self.assert_aws_creds_from_env(self.run_script("storage_cleanup_daily"))

    def test_user_activity_daily(self):
        kind, _, kwargs = self.run_script("user_activity_daily")
        self.assertEqual(kind, "psycopg2")
        self.assertEqual(kwargs["password"], "db-secret-env")
        self.assertEqual(kwargs["host"], "db.from-file")

    def test_search_reindex_weekly(self):
        kind, _, kwargs = self.run_script("search_reindex_weekly")
        self.assertEqual(kind, "requests")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer meili-secret-env")

    def test_script_fails_without_db_password(self):
        os.environ.pop("ETL_DB_PASSWORD")
        sys.modules.pop("user_activity_daily", None)
        module = importlib.import_module("user_activity_daily")
        with mock.patch("builtins.print"), self.assertRaises(etl_config.MissingSettingError):
            module.main()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
