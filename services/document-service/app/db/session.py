"""Database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base


def engine_connect_args(statement_timeout_ms: int) -> dict[str, dict[str, str]]:
    """asyncpg connect arguments; a positive timeout is set on every pooled connection."""
    if statement_timeout_ms > 0:
        return {"server_settings": {"statement_timeout": str(statement_timeout_ms)}}
    return {}


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    connect_args=engine_connect_args(settings.db_statement_timeout_ms),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
