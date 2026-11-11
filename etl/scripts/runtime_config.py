"""Shared configuration for cron ETL jobs."""

import configparser
import os
from pathlib import Path


def required_secret(name):
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f"Required ETL secret {name} is missing or empty")
    return value


def load_config():
    path = Path(os.environ.get("ETL_CONFIG_PATH", "/opt/etl/config.ini"))
    config = configparser.ConfigParser()
    if not config.read(path):
        raise RuntimeError(f"ETL configuration not found: {path}")
    return config
