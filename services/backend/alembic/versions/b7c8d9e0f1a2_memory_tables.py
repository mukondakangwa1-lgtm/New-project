"""kudos memory tables: kudos_memories

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-08 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def get_vector_type():
    """Return pgvector Vector type when available, else a plain TEXT column
    so the table still exists without the extension (keyword fallback)."""
    try:
        from pgvector.sqlalchemy import Vector
        return Vector(1536)
    except Exception:
        return sa.Text()


def upgrade() -> None:
    """Apply this migration."""
    op.create_table('kudos_memories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('layer', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('embedding', get_vector_type(), nullable=True),
    sa.Column('importance', sa.Float(), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=120), nullable=True),
    sa.Column('access_count', sa.Integer(), nullable=True),
    sa.Column('last_access_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kudos_memories_user_id'), 'kudos_memories', ['user_id'], unique=False)
    op.create_index(op.f('ix_kudos_memories_layer'), 'kudos_memories', ['layer'], unique=False)


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index(op.f('ix_kudos_memories_layer'), table_name='kudos_memories')
    op.drop_index(op.f('ix_kudos_memories_user_id'), table_name='kudos_memories')
    op.drop_table('kudos_memories')