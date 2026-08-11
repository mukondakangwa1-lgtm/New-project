"""voice_sessions table + voice_samples.session_id

Interactive signature-voice session: KUDOS greets, the superadmin speaks their
lines back, KUDOS draft-clones the accumulated audio and re-speaks each line in
that draft voice, then the session finalizes into the live signature voice.

Revision ID: a0b1c2d3e4f9
Revises: c2d3e4f5a6b8
Create Date: 2026-08-11 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f9'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        'voice_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('voice_profiles.id'), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),  # active | finalized | cancelled
        sa.Column('draft_voice_id', sa.String(length=160), nullable=True),  # ElevenLabs draft clone id
        sa.Column('turn_count', sa.Integer(), nullable=True),
        sa.Column('total_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('finalized_at', sa.DateTime(), nullable=True),
    )
    op.add_column('voice_samples', sa.Column('session_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Revert this migration."""
    op.drop_column('voice_samples', 'session_id')
    op.drop_table('voice_sessions')
