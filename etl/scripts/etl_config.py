"""Shared configuration loader for the OtterWorks ETL scripts (ETL-142).

Non-secret settings (bucket names, service URLs, region, database host) come
from an INI file -- ``$ETL_CONFIG_PATH`` or ``/opt/etl/config.ini`` -- which is
deployed per host and never committed (see ``config.ini.example``).

Every option can be overridden by an environment variable. Credentials are
expected to arrive via the environment (``/opt/etl/.env`` sourced by
``run.sh``, the cron environment, or a secrets manager injecting env vars):

    [aws] access_key           AWS_ACCESS_KEY_ID
    [aws] secret_key           AWS_SECRET_ACCESS_KEY
    [aws] region               AWS_REGION / AWS_DEFAULT_REGION
    [database] password        ETL_DB_PASSWORD
    [services] meilisearch_api_key   MEILISEARCH_API_KEY

and generically ``ETL_<SECTION>_<OPTION>`` (e.g. ``ETL_DATABASE_HOST``).
Empty values are treated as unset. AWS keys are optional: when unset, boto3
falls back to its default credential chain (instance profile / IRSA).
"""

import configparser
import os

DEFAULT_CONFIG_PATH = "/opt/etl/config.ini"
CONFIG_PATH_ENV = "ETL_CONFIG_PATH"

ENV_ALIASES = {
    ("aws", "access_key"): ("AWS_ACCESS_KEY_ID",),
    ("aws", "secret_key"): ("AWS_SECRET_ACCESS_KEY",),
    ("aws", "region"): ("AWS_REGION", "AWS_DEFAULT_REGION"),
    ("database", "password"): ("ETL_DB_PASSWORD",),
    ("services", "meilisearch_api_key"): ("MEILISEARCH_API_KEY", "MEILI_MASTER_KEY"),
}


class MissingSettingError(RuntimeError):
    pass


def env_names(section, option):
    generic = f"ETL_{section.upper()}_{option.upper()}"
    return (generic,) + ENV_ALIASES.get((section, option), ())


class EtlConfig:
    def __init__(self, path=None, environ=None):
        self.environ = os.environ if environ is None else environ
        self.path = path or self.environ.get(CONFIG_PATH_ENV) or DEFAULT_CONFIG_PATH
        self.parser = configparser.ConfigParser()
        self.parser.read(self.path)

    def get(self, section, option, required=True):
        for name in env_names(section, option):
            value = self.environ.get(name)
            if value:
                return value
        value = self.parser.get(section, option, fallback="").strip()
        if value:
            return value
        if required:
            names = ", ".join(env_names(section, option))
            raise MissingSettingError(
                f"Missing ETL setting [{section}] {option}: set one of {names} or add it to {self.path}"
            )
        return None

    def getint(self, section, option, required=True):
        value = self.get(section, option, required=required)
        return int(value) if value is not None else None


def load_config(path=None, environ=None):
    return EtlConfig(path=path, environ=environ)
