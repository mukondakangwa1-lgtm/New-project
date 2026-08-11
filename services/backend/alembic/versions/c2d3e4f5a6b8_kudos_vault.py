"""KUDOS knowledge vault + constitution

The vault gives KUDOS a single searchable place for everything it knows:
superadmin-curated canonical articles (source_type=curated) plus indexed
mirrors of approved documents, web knowledge and memories
(source_type=document|web|memory). The constitution is KUDOS's grounding
policy — the rules it always obeys when it answers.

Revision ID: c2d3e4f5a6b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-11 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kudos_vault_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=60), nullable=False, server_default="general"),
        sa.Column("tags", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="curated"),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("search_text", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kudos_vault_entries_title", "kudos_vault_entries", ["title"])
    op.create_index("ix_kudos_vault_entries_category", "kudos_vault_entries", ["category"])
    op.create_index("ix_kudos_vault_entries_source_type", "kudos_vault_entries", ["source_type"])
    op.create_index("ix_kudos_vault_entries_author_id", "kudos_vault_entries", ["author_id"])
    op.create_index("ix_kudos_vault_entries_user_id", "kudos_vault_entries", ["user_id"])

    op.create_table(
        "kudos_constitution",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kudos_constitution_article_id", "kudos_constitution", ["article_id"])


def downgrade() -> None:
    op.drop_index("ix_kudos_constitution_article_id", table_name="kudos_constitution")
    op.drop_table("kudos_constitution")
    op.drop_index("ix_kudos_vault_entries_user_id", table_name="kudos_vault_entries")
    op.drop_index("ix_kudos_vault_entries_author_id", table_name="kudos_vault_entries")
    op.drop_index("ix_kudos_vault_entries_source_type", table_name="kudos_vault_entries")
    op.drop_index("ix_kudos_vault_entries_category", table_name="kudos_vault_entries")
    op.drop_index("ix_kudos_vault_entries_title", table_name="kudos_vault_entries")
    op.drop_table("kudos_vault_entries")