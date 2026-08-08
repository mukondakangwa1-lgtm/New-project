"""kudos device storage: kudos_devices, kudos_memory_replicas + policy column

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-08-08 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.add_column('kudos_memories', sa.Column('device_policy', sa.String(length=20),
                                              nullable=True, server_default='replicated'))

    op.create_table('kudos_devices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('platform', sa.String(length=30), nullable=True),
    sa.Column('api_token', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('storage_bytes', sa.Integer(), nullable=True),
    sa.Column('used_storage_bytes', sa.Integer(), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kudos_devices_user_id'), 'kudos_devices', ['user_id'], unique=False)
    op.create_index(op.f('ix_kudos_devices_api_token'), 'kudos_devices', ['api_token'], unique=False)

    op.create_table('kudos_memory_replicas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('memory_id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('synced_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['kudos_devices.id'], ),
    sa.ForeignKeyConstraint(['memory_id'], ['kudos_memories.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kudos_memory_replicas_user_id'), 'kudos_memory_replicas', ['user_id'], unique=False)
    op.create_index(op.f('ix_kudos_memory_replicas_memory_id'), 'kudos_memory_replicas', ['memory_id'], unique=False)
    op.create_index(op.f('ix_kudos_memory_replicas_device_id'), 'kudos_memory_replicas', ['device_id'], unique=False)


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index(op.f('ix_kudos_memory_replicas_device_id'), table_name='kudos_memory_replicas')
    op.drop_index(op.f('ix_kudos_memory_replicas_memory_id'), table_name='kudos_memory_replicas')
    op.drop_index(op.f('ix_kudos_memory_replicas_user_id'), table_name='kudos_memory_replicas')
    op.drop_table('kudos_memory_replicas')
    op.drop_index(op.f('ix_kudos_devices_api_token'), table_name='kudos_devices')
    op.drop_index(op.f('ix_kudos_devices_user_id'), table_name='kudos_devices')
    op.drop_table('kudos_devices')
    op.drop_column('kudos_memories', 'device_policy')