"""Load runtime secrets without shell evaluation or a plaintext env file."""

import argparse
import json
import os
from pathlib import Path
import runpy

import boto3

from runtime_config import load_config, required_secret

JOBS = (
    "analytics_daily.py",
    "audit_archive_weekly.py",
    "search_reindex_weekly.py",
    "storage_cleanup_daily.py",
    "user_activity_daily.py",
)
SECRET_NAMES = ("ETL_DB_PASSWORD", "ETL_MEILISEARCH_API_KEY")


def populate_secrets(client):
    secret_id = os.environ.get("ETL_SECRET_ID", "otterworks/etl/runtime")
    response = client.get_secret_value(SecretId=secret_id)
    try:
        values = json.loads(response["SecretString"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("ETL runtime secret must be a JSON object in SecretString") from error
    if not isinstance(values, dict):
        raise RuntimeError("ETL runtime secret must be a JSON object")
    for name in SECRET_NAMES:
        value = values.get(name)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"ETL runtime secret must contain nonempty {name}")
    for name in SECRET_NAMES:
        os.environ[name] = values[name]
        required_secret(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=JOBS)
    args = parser.parse_args()
    config = load_config()
    client = boto3.client("secretsmanager", region_name=config.get("aws", "region"))
    populate_secrets(client)
    runpy.run_path(str(Path(__file__).with_name(args.job)), run_name="__main__")


if __name__ == "__main__":
    main()
