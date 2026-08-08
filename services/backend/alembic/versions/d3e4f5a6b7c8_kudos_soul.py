"""kudos soul + terminal tables: kudos_soul, kudos_terminal_sessions, kudos_terminal_commands

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-08-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table('kudos_soul',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=True),
    sa.Column('personality', sa.Text(), nullable=True),
    sa.Column('values', sa.Text(), nullable=True),
    sa.Column('desires', sa.Text(), nullable=True),
    sa.Column('dreams', sa.Text(), nullable=True),
    sa.Column('goals', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('kudos_terminal_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('device_id', sa.Integer(), sa.ForeignKey('kudos_devices.id'), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('workspace', sa.String(length=300), nullable=True),
    sa.Column('opened_by', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_kudos_terminal_sessions_id', 'kudos_terminal_sessions', ['id'])
    op.create_index('ix_kudos_terminal_sessions_user_id', 'kudos_terminal_sessions', ['user_id'])
    op.create_index('ix_kudos_terminal_sessions_device_id', 'kudos_terminal_sessions', ['device_id'])

    op.create_table('kudos_terminal_commands',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), sa.ForeignKey('kudos_terminal_sessions.id'), nullable=False),
    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('device_id', sa.Integer(), sa.ForeignKey('kudos_devices.id'), nullable=True),
    sa.Column('command', sa.Text(), nullable=False),
    sa.Column('language', sa.String(length=20), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('exit_code', sa.Integer(), nullable=True),
    sa.Column('output', sa.Text(), nullable=True),
    sa.Column('approved_by', sa.Integer(), nullable=True),
    sa.Column('claimed_at', sa.DateTime(), nullable=True),
    sa.Column('requested_at', sa.DateTime(), nullable=True),
    sa.Column('executed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_kudos_terminal_commands_id', 'kudos_terminal_commands', ['id'])
    op.create_index('ix_kudos_terminal_commands_session_id', 'kudos_terminal_commands', ['session_id'])
    op.create_index('ix_kudos_terminal_commands_user_id', 'kudos_terminal_commands', ['user_id'])


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index('ix_kudos_terminal_commands_user_id', table_name='kudos_terminal_commands')
    op.drop_index('ix_kudos_terminal_commands_session_id', table_name='kudos_terminal_commands')
    op.drop_index('ix_kudos_terminal_commands_id', table_name='kudos_terminal_commands')
    op.drop_table('kudos_terminal_commands')
    op.drop_index('ix_kudos_terminal_sessions_device_id', table_name='kudos_terminal_sessions')
    op.drop_index('ix_kudos_terminal_sessions_user_id', table_name='kudos_terminal_sessions')
    op.drop_index('ix_kudos_terminal_sessions_id', table_name='kudos_terminal_sessions')
    op.drop_table('kudos_terminal_sessions')
    op.drop_table('kudos_soul')