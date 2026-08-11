"""kudos_governance: rotating superadmin identity + succession

Revision ID: e6f7a8b9c0d1
Revises: f2a3b4c5d6e7
Create Date: 2026-08-10 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        'kudos_governance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('superadmin_user_id', sa.Integer(), nullable=True),
        sa.Column('uid', sa.String(length=120), nullable=True),
        sa.Column('previous_uids', sa.Text(), nullable=True),
        sa.Column('uid_rotates_every_days', sa.Integer(), nullable=True),
        sa.Column('last_rotation_at', sa.DateTime(), nullable=True),
        sa.Column('next_rotation_at', sa.DateTime(), nullable=True),
        sa.Column('last_superadmin_login_at', sa.DateTime(), nullable=True),
        sa.Column('succession_inactive_days', sa.Integer(), nullable=True),
        sa.Column('revival_years', sa.Integer(), nullable=True),
        sa.Column('cloud_target', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Revert this migration."""
    op.drop_table('kudos_governance')
