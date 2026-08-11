"""kudos_voices library + voice_profiles signature columns

KUDOS voice library: every voice KUDOS can speak with (cloned signature,
additional clones, stock voices). voice_profiles now points at one library
voice as the signature and tracks the donating device + pending state.

Revision ID: f3a4b5c6d7e8
Revises: e6f7a8b9c0d1
Create Date: 2026-08-11 08:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        'kudos_voices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=True),
        sa.Column('provider', sa.String(length=30), nullable=True),
        sa.Column('provider_voice_id', sa.String(length=160), nullable=True),
        sa.Column('source_device_id', sa.Integer(), nullable=True),
        sa.Column('sample_keys', sa.Text(), nullable=True),
        sa.Column('is_signature', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.add_column('voice_profiles', sa.Column('signature_voice_id', sa.Integer(), nullable=True))
    op.add_column('voice_profiles', sa.Column('signature_state', sa.String(length=20), nullable=True))
    op.add_column('voice_profiles', sa.Column('owner_device_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Revert this migration."""
    op.drop_column('voice_profiles', 'owner_device_id')
    op.drop_column('voice_profiles', 'signature_state')
    op.drop_column('voice_profiles', 'signature_voice_id')
    op.drop_table('kudos_voices')
