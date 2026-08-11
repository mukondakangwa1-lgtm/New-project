"""kudos_brain: persistent offline brain store

Revision ID: f2a3b4c5d6e7
Revises: e5f6a7b8c9d0
Create Date: 2026-08-10 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        'kudos_brain',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=80), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(length=40), nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_title', sa.String(length=255), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('times_learned', sa.Integer(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_kudos_brain_id', 'kudos_brain', ['id'])
    op.create_index('ix_kudos_brain_user_id', 'kudos_brain', ['user_id'])


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index('ix_kudos_brain_user_id', table_name='kudos_brain')
    op.drop_index('ix_kudos_brain_id', table_name='kudos_brain')
    op.drop_table('kudos_brain')
