"""Index document list filters and version ordering."""

from alembic import op

revision = "004_document_list_indexes"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_owner_list", "documents",
        ["owner_id", "is_deleted", "is_template", "updated_at"],
    )
    op.create_index(
        "ix_document_versions_document_version", "document_versions",
        ["document_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_versions_document_version", table_name="document_versions")
    op.drop_index("ix_documents_owner_list", table_name="documents")
