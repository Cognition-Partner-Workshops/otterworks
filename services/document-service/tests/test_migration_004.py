"""Migration 004 adds folder_digests and adds no index on documents.folder_id."""

import asyncio
import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

SERVICE_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_URL = os.environ.get("DOC_SVC_TEST_POSTGRES_URL")


def _load_004() -> ModuleType:
    path = SERVICE_ROOT / "alembic" / "versions" / "004_folder_digests.py"
    spec = importlib.util.spec_from_file_location("migration_004", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(conn: Connection, fn_name: str) -> None:
    migration = _load_004()
    with Operations.context(MigrationContext.configure(conn)):
        getattr(migration, fn_name)()


def test_revision_chain() -> None:
    migration = _load_004()
    assert (migration.revision, migration.down_revision) == ("004", "003")


def test_upgrade_then_downgrade() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        _run(conn, "upgrade")
        columns = {c["name"]: c for c in inspect(conn).get_columns("folder_digests")}
        assert list(columns) == ["folder_id", "documents_total", "last_updated_at", "computed_at"]
        assert not columns["documents_total"]["nullable"]
        assert columns["last_updated_at"]["nullable"]
        assert not columns["computed_at"]["nullable"]
        assert columns["computed_at"]["default"] is not None
        assert inspect(conn).get_pk_constraint("folder_digests")["constrained_columns"] == [
            "folder_id"
        ]

        _run(conn, "downgrade")
        assert "folder_digests" not in inspect(conn).get_table_names()


def _pg_tables_and_document_indexes(url: str) -> tuple[set[str], set[tuple[str, ...]]]:
    async def read() -> tuple[set[str], set[tuple[str, ...]]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(
                    lambda sync: (
                        set(inspect(sync).get_table_names()),
                        {
                            tuple(ix["column_names"])
                            for ix in inspect(sync).get_indexes("documents")
                        },
                    )
                )
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.skipif(not POSTGRES_URL, reason="DOC_SVC_TEST_POSTGRES_URL not set")
def test_postgres_upgrade_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    assert POSTGRES_URL
    monkeypatch.setattr("app.config.settings.database_url", POSTGRES_URL)
    cfg = Config(str(SERVICE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))

    command.upgrade(cfg, "head")
    try:
        tables, indexes = _pg_tables_and_document_indexes(POSTGRES_URL)
        assert "folder_digests" in tables
        assert ("folder_id",) not in indexes
        command.downgrade(cfg, "003")
        tables, _ = _pg_tables_and_document_indexes(POSTGRES_URL)
        assert "folder_digests" not in tables
    finally:
        command.upgrade(cfg, "head")
