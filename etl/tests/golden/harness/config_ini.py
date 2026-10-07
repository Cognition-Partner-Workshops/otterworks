"""Generates the /opt/etl/config.ini mounted into the legacy container.

The committed etl/config.ini holds production-looking values and is never
read; this file only ever contains local endpoints and dev credentials.
"""

from __future__ import annotations

import configparser
import io

from . import settings


def render(services_url: str, overrides: dict | None = None) -> str:
    config = configparser.ConfigParser()
    config["aws"] = {
        "access_key": settings.AWS_ACCESS_KEY,
        "secret_key": settings.AWS_SECRET_KEY,
        "region": settings.AWS_REGION,
    }
    config["database"] = {
        "host": settings.PG_HOST,
        "port": str(settings.PG_PORT),
        "database": settings.PG_DB,
        "user": settings.PG_USER,
        "password": settings.PG_PASSWORD,
    }
    config["s3"] = dict(settings.S3_CONFIG)
    config["services"] = {
        "document_service_url": "%s/document-service" % services_url,
        "file_service_url": "%s/file-service" % services_url,
        "meilisearch_url": settings.MEILI_URL,
        "meilisearch_api_key": settings.MEILI_API_KEY,
    }
    for section, values in (overrides or {}).items():
        if values is None:
            config.remove_section(section)
            continue
        if not config.has_section(section):
            config.add_section(section)
        for key, value in values.items():
            if value is None:
                config.remove_option(section, key)
            else:
                config.set(section, key, str(value))
    out = io.StringIO()
    config.write(out)
    return out.getvalue()
