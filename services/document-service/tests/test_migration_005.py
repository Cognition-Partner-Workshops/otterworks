"""Migration 005 indexes documents (folder_id, updated_at DESC) for folder reads."""

import asyncio
import importlib.util
import os
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations

SERVICE_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_URL = os.environ.get("DOC_SVC_TEST_POSTGRES_URL")
INDEX_NAME = "ix_documents_folder_id_updated_at"


def _load_005() -> ModuleType:
    path = SERVICE_ROOT / "alembic" / "versions" / "005_documents_folder_id_updated_at_index.py"
    spec = importlib.util.spec_from_file_location("migration_005", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(conn: Connection, fn_name: str) -> None:
    migration = _load_005()
    with Operations.context(MigrationContext.configure(conn)):
        getattr(migration, fn_name)()


def _document_indexes(conn: Connection) -> dict[str, dict]:
    return {ix["name"]: ix for ix in inspect(conn).get_indexes("documents")}


def test_revision_chain() -> None:
    migration = _load_005()
    assert (migration.revision, migration.down_revision) == ("005", "004")
    assert migration.INDEX_NAME == INDEX_NAME


def test_upgrade_then_downgrade() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE documents ("
                "id TEXT PRIMARY KEY, folder_id TEXT, updated_at TIMESTAMP NOT NULL)"
            )
        )
        _run(conn, "upgrade")
        assert INDEX_NAME in _document_indexes(conn)

        _run(conn, "downgrade")
        assert INDEX_NAME not in _document_indexes(conn)


def test_model_declares_the_same_index() -> None:
    from app.models.document import Document

    index = next(ix for ix in Document.__table__.indexes if ix.name == INDEX_NAME)
    assert [str(expr) for expr in index.expressions] == ["documents.folder_id", "updated_at DESC"]


def _pg_index_scan_plans(url: str) -> tuple[dict[str, str], list[str], list[str]]:
    folder_id = uuid.uuid4()

    async def read() -> tuple[dict[str, str], list[str], list[str]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                defs = {
                    name: definition
                    for name, definition in (
                        await conn.execute(
                            text(
                                "SELECT indexname, indexdef FROM pg_indexes "
                                "WHERE tablename = 'documents'"
                            )
                        )
                    ).all()
                }
                await conn.execute(text("SET LOCAL enable_seqscan = off"))
                digest_plan = [
                    row[0]
                    for row in (
                        await conn.execute(
                            text(
                                "EXPLAIN SELECT count(*), max(updated_at) FROM documents "
                                "WHERE folder_id = :folder_id AND is_deleted = false"
                            ),
                            {"folder_id": folder_id},
                        )
                    ).all()
                ]
                listing_plan = [
                    row[0]
                    for row in (
                        await conn.execute(
                            text(
                                "EXPLAIN SELECT * FROM documents "
                                "WHERE folder_id = :folder_id AND is_deleted = false "
                                "ORDER BY updated_at DESC LIMIT 50"
                            ),
                            {"folder_id": folder_id},
                        )
                    ).all()
                ]
                await conn.rollback()
                return defs, digest_plan, listing_plan
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
        defs, digest_plan, listing_plan = _pg_index_scan_plans(POSTGRES_URL)
        assert defs[INDEX_NAME].endswith("USING btree (folder_id, updated_at DESC)")
        assert any(INDEX_NAME in line for line in digest_plan), digest_plan
        assert any(INDEX_NAME in line for line in listing_plan), listing_plan
        assert not any("Sort" in line for line in listing_plan), listing_plan

        command.downgrade(cfg, "004")
        defs, _, _ = _pg_index_scan_plans(POSTGRES_URL)
        assert INDEX_NAME not in defs
    finally:
        command.upgrade(cfg, "head")
