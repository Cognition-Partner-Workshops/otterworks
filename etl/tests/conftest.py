import configparser
import importlib.util
import uuid
from pathlib import Path

import pytest
from moto import mock_dynamodb, mock_s3, mock_sqs

ETL_DIR = Path(__file__).resolve().parents[1]
LEGACY_CONFIG_PATH = "/opt/etl/config.ini"


class EtlConfig:
    """Copy of etl/config.ini that the scripts read instead of /opt/etl/config.ini."""

    def __init__(self, path):
        self.path = path
        self.parser = configparser.ConfigParser()
        self.parser.read(ETL_DIR / "config.ini")
        self._write()

    def set(self, section, option, value):
        self.parser.set(section, option, str(value))
        self._write()

    def _write(self):
        with open(self.path, "w") as fh:
            self.parser.write(fh)


@pytest.fixture
def etl_config(tmp_path, monkeypatch):
    config = EtlConfig(tmp_path / "config.ini")
    real_read = configparser.ConfigParser.read

    def read(self, filenames, encoding=None):
        if filenames == LEGACY_CONFIG_PATH:
            filenames = str(config.path)
        return real_read(self, filenames, encoding)

    monkeypatch.setattr(configparser.ConfigParser, "read", read)
    return config


@pytest.fixture
def aws(monkeypatch):
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_s3(), mock_sqs(), mock_dynamodb():
        yield


def load_script(name):
    path = ETL_DIR / "scripts" / ("%s.py" % name)
    spec = importlib.util.spec_from_file_location("%s_%s" % (name, uuid.uuid4().hex), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
