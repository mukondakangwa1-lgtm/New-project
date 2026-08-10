"""speaking_sessions.audio_mime: store the real audio container format

Revision ID: d5e6f7a8b9c0
Revises: c0a1b2d3e4f5
Create Date: 2026-08-10 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c0a1b2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.add_column('speaking_sessions', sa.Column('audio_mime', sa.String(length=60), nullable=False, server_default=''))


def downgrade() -> None:
    """Revert this migration."""
    op.drop_column('speaking_sessions', 'audio_mime')
