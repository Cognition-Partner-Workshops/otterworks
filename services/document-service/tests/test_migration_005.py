"""Migration 005 indexes documents by folder so folder counts and listings use an index scan."""

import asyncio
import importlib.util
import json
import os
import uuid
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations

SERVICE_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_URL = os.environ.get("DOC_SVC_TEST_POSTGRES_URL")
INDEX_NAME = "ix_documents_folder_id_updated_at"
OWNER = uuid.UUID("6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7005")
FOLDERS = 200
DOCUMENTS = 20_000


def _load_005() -> ModuleType:
    path = SERVICE_ROOT / "alembic" / "versions" / "005_documents_folder_index.py"
    spec = importlib.util.spec_from_file_location("migration_005", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(conn: Connection, fn_name: str) -> None:
    migration = _load_005()
    with Operations.context(MigrationContext.configure(conn)):
        getattr(migration, fn_name)()


def _index_names(conn: Connection) -> set[str]:
    return {ix["name"] for ix in inspect(conn).get_indexes("documents")}


def test_revision_chain() -> None:
    migration = _load_005()
    assert (migration.revision, migration.down_revision) == ("005", "004")


def test_upgrade_then_downgrade() -> None:
    engine = create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "documents",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("folder_id", sa.String(36)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    with engine.begin() as conn:
        metadata.create_all(conn)
        _run(conn, "upgrade")
        assert INDEX_NAME in _index_names(conn)

        _run(conn, "downgrade")
        assert INDEX_NAME not in _index_names(conn)


def _plan_index_names(plan: dict) -> set[str]:
    names = {plan["Index Name"]} if "Index Name" in plan else set()
    for child in plan.get("Plans", []):
        names |= _plan_index_names(child)
    return names


def _pg_index_def_and_count_plan(url: str) -> tuple[str | None, set[str]]:
    async def read() -> tuple[str | None, set[str]]:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO documents (id, title, owner_id, folder_id, updated_at) "
                        "SELECT gen_random_uuid(), 'idx 005 ' || g, :owner, f.id, "
                        "now() - g * interval '1 second' "
                        "FROM generate_series(1, :n) g "
                        "JOIN (SELECT n, gen_random_uuid() AS id "
                        "FROM generate_series(1, :folders) n) f "
                        "ON f.n = 1 + g % :folders"
                    ),
                    {"owner": OWNER, "n": DOCUMENTS, "folders": FOLDERS},
                )
            async with engine.connect() as conn:
                await conn.execute(text("ANALYZE documents"))
                indexdef = (
                    await conn.execute(
                        text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
                        {"name": INDEX_NAME},
                    )
                ).scalar_one_or_none()
                folder_id = (
                    await conn.execute(
                        text("SELECT folder_id FROM documents WHERE owner_id = :owner LIMIT 1"),
                        {"owner": OWNER},
                    )
                ).scalar_one()
                plan = (
                    await conn.execute(
                        text(
                            "EXPLAIN (FORMAT JSON) SELECT count(*), max(updated_at) "
                            "FROM documents WHERE folder_id = :folder AND is_deleted = false"
                        ),
                        {"folder": folder_id},
                    )
                ).scalar_one()
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM documents WHERE owner_id = :owner"), {"owner": OWNER}
                )
            if isinstance(plan, str):
                plan = json.loads(plan)
            return indexdef, _plan_index_names(plan[0]["Plan"])
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.skipif(not POSTGRES_URL, reason="DOC_SVC_TEST_POSTGRES_URL not set")
def test_postgres_folder_count_uses_index(monkeypatch: pytest.MonkeyPatch) -> None:
    assert POSTGRES_URL
    monkeypatch.setattr("app.config.settings.database_url", POSTGRES_URL)
    cfg = Config(str(SERVICE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))

    command.upgrade(cfg, "005")
    try:
        indexdef, plan_indexes = _pg_index_def_and_count_plan(POSTGRES_URL)
        assert indexdef is not None
        assert indexdef.endswith("USING btree (folder_id, updated_at DESC)")
        assert INDEX_NAME in plan_indexes
        command.downgrade(cfg, "004")
        indexdef, plan_indexes = _pg_index_def_and_count_plan(POSTGRES_URL)
        assert indexdef is None
        assert INDEX_NAME not in plan_indexes
    finally:
        command.upgrade(cfg, "head")
