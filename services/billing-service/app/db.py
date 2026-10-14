from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings


@lru_cache(maxsize=1)
def client() -> MongoClient:
    return MongoClient(settings.mongodb_uri, uuidRepresentation="standard")


def database() -> Database:
    return client()[settings.mongodb_database]


def reset() -> None:
    from app.load import load

    if not settings.source_dsn:
        raise RuntimeError("BILLING_SVC_SOURCE_DSN is required to reset the collections")
    load(settings.source_dsn, database())
