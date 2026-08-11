"""student fields on users + content_progress table

Adds User.is_student / User.school (student opt-in, school-gated Courses and
Register) and the ContentProgress table that powers the dashboard's
"continue where you left off" for movies, books and audio.

Revision ID: e7f8a9b0c1d2
Revises: a0b1c2d3e4f9
Create Date: 2026-08-11 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.add_column('users', sa.Column('is_student', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('school', sa.String(length=255), nullable=True))
    op.create_table(
        'content_progress',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('content_key', sa.String(length=255), nullable=False, index=True),
        sa.Column('kind', sa.String(length=20), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=True),
        sa.Column('url', sa.String(length=600), nullable=True),
        sa.Column('position_pct', sa.Float(), nullable=True),
        sa.Column('detail', sa.String(length=600), nullable=True),
        sa.Column('source', sa.String(length=60), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Revert this migration."""
    op.drop_table('content_progress')
    op.drop_column('users', 'school')
    op.drop_column('users', 'is_student')
