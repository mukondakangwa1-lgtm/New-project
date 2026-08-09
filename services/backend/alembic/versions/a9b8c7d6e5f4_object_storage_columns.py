"""object storage columns: kudos_documents.storage_key, user_profiles.avatar_url

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-08-09 08:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.add_column('kudos_documents', sa.Column('storage_key', sa.String(length=255), nullable=True, server_default=''))
    op.add_column('user_profiles', sa.Column('avatar_url', sa.String(length=255), nullable=True, server_default=''))


def downgrade() -> None:
    """Revert this migration."""
    op.drop_column('user_profiles', 'avatar_url')
    op.drop_column('kudos_documents', 'storage_key')