"""kudos agent tables: sandbox proposals, sandbox logs, agent tasks

Revision ID: f1a2b3c4d5e6
Revises: d3e4f5a6b7c8
Create Date: 2026-08-08 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table('kudos_sandbox_proposals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('priority', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('source', sa.String(length=50), nullable=True),
    sa.Column('workspace', sa.String(length=300), nullable=True),
    sa.Column('branch', sa.String(length=120), nullable=True),
    sa.Column('commit_hash', sa.String(length=64), nullable=True),
    sa.Column('files_changed', sa.Text(), nullable=True),
    sa.Column('analysis', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uuid')
    )
    op.create_index(op.f('ix_kudos_sandbox_proposals_id'), 'kudos_sandbox_proposals', ['id'], unique=False)
    op.create_index(op.f('ix_kudos_sandbox_proposals_uuid'), 'kudos_sandbox_proposals', ['uuid'], unique=True)

    op.create_table('kudos_sandbox_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workspace', sa.String(length=300), nullable=True),
    sa.Column('operation', sa.String(length=80), nullable=False),
    sa.Column('command', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('exit_code', sa.Integer(), nullable=True),
    sa.Column('output', sa.Text(), nullable=True),
    sa.Column('proposal_uuid', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kudos_sandbox_logs_id'), 'kudos_sandbox_logs', ['id'], unique=False)
    op.create_index(op.f('ix_kudos_sandbox_logs_proposal_uuid'), 'kudos_sandbox_logs', ['proposal_uuid'], unique=False)

    op.create_table('kudos_agent_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_type', sa.String(length=80), nullable=False),
    sa.Column('payload', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('result', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kudos_agent_tasks_id'), 'kudos_agent_tasks', ['id'], unique=False)


def downgrade() -> None:
    """Revert this migration."""
    op.drop_table('kudos_agent_tasks')
    op.drop_table('kudos_sandbox_logs')
    op.drop_table('kudos_sandbox_proposals')
