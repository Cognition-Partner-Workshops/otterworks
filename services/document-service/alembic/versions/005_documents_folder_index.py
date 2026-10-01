"""Index documents by folder for folder listings and the folder-digest worker.

Revision ID: 005
Revises: 004
Create Date: 2026-10-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_documents_folder_id_updated_at"


def upgrade() -> None:
    op.create_index(INDEX_NAME, "documents", ["folder_id", sa.text("updated_at DESC")])


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="documents")
