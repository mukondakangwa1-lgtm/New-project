"""voice_profiles + voice_samples: KUDOS signature voice store

Revision ID: e5f6a7b8c9d0
Revises: d5e6f7a8b9c0
Create Date: 2026-08-10 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        'voice_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('tts_enabled', sa.Boolean(), nullable=True),
        sa.Column('cloned_voice_id', sa.String(length=120), nullable=True),
        sa.Column('default_voice', sa.String(length=120), nullable=True),
        sa.Column('signature_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'voice_samples',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('storage_key', sa.String(length=255), nullable=True),
        sa.Column('mime', sa.String(length=60), nullable=True),
        sa.Column('transcribed', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Revert this migration."""
    op.drop_table('voice_samples')
    op.drop_table('voice_profiles')
