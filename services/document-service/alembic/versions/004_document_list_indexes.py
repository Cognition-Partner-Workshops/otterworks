"""Add indexes supporting document list queries.

Revision ID: 004_document_list_indexes
Revises: 003
Create Date: 2025-01-22 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "004_document_list_indexes"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_owner_active_updated",
        "documents",
        ["owner_id", "is_deleted", "is_template", "updated_at"],
    )
    op.create_index(
        "ix_document_versions_document_version",
        "document_versions",
        ["document_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_versions_document_version", table_name="document_versions")
    op.drop_index("ix_documents_owner_active_updated", table_name="documents")
