"""users.is_approved — admin-approved registrations; guest chat keys

Revision ID: e1f2a3b4c5d6
Revises: a9b8c7d6e5f4
Create Date: 2026-08-09 09:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.add_column('users', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('kudos_conversations', sa.Column('guest_key', sa.String(length=64), nullable=True))
    op.create_index('ix_kudos_conversations_guest_key', 'kudos_conversations', ['guest_key'])


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index('ix_kudos_conversations_guest_key', table_name='kudos_conversations')
    op.drop_column('kudos_conversations', 'guest_key')
    op.drop_column('users', 'is_approved')