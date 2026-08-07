"""studio tables: speaking, broadcasts, calls, journal, signaling

Revision ID: a1b2c3d4e5f6
Revises: 39101dd01b2e
Create Date: 2026-08-07 23:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '39101dd01b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table('speaking_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('difficulty', sa.String(length=20), nullable=True),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('duration_spoken', sa.Integer(), nullable=True),
    sa.Column('self_rating', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('audio_url', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_speaking_sessions_id'), 'speaking_sessions', ['id'], unique=False)
    op.create_table('broadcasts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('host_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('listeners', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['host_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_broadcasts_id'), 'broadcasts', ['id'], unique=False)
    op.create_table('video_calls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('host_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('is_group', sa.Boolean(), nullable=True),
    sa.Column('max_participants', sa.Integer(), nullable=True),
    sa.Column('enable_whiteboard', sa.Boolean(), nullable=True),
    sa.Column('enable_screen_share', sa.Boolean(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['host_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_calls_id'), 'video_calls', ['id'], unique=False)
    op.create_table('call_participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('call_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=True),
    sa.Column('joined_at', sa.DateTime(), nullable=True),
    sa.Column('left_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['call_id'], ['video_calls.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_participants_id'), 'call_participants', ['id'], unique=False)
    op.create_table('whiteboard_strokes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('call_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('data', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['call_id'], ['video_calls.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whiteboard_strokes_id'), 'whiteboard_strokes', ['id'], unique=False)
    op.create_table('webrtc_signals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('room_type', sa.String(length=20), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('signal_type', sa.String(length=20), nullable=False),
    sa.Column('payload', sa.Text(), nullable=False),
    sa.Column('is_consumed', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webrtc_signals_id'), 'webrtc_signals', ['id'], unique=False)
    op.create_table('journal_blocks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('block_type', sa.String(length=30), nullable=True),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_journal_blocks_id'), 'journal_blocks', ['id'], unique=False)


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index(op.f('ix_journal_blocks_id'), table_name='journal_blocks')
    op.drop_table('journal_blocks')
    op.drop_index(op.f('ix_webrtc_signals_id'), table_name='webrtc_signals')
    op.drop_table('webrtc_signals')
    op.drop_index(op.f('ix_whiteboard_strokes_id'), table_name='whiteboard_strokes')
    op.drop_table('whiteboard_strokes')
    op.drop_index(op.f('ix_call_participants_id'), table_name='call_participants')
    op.drop_table('call_participants')
    op.drop_index(op.f('ix_video_calls_id'), table_name='video_calls')
    op.drop_table('video_calls')
    op.drop_index(op.f('ix_broadcasts_id'), table_name='broadcasts')
    op.drop_table('broadcasts')
    op.drop_index(op.f('ix_speaking_sessions_id'), table_name='speaking_sessions')
    op.drop_table('speaking_sessions')
