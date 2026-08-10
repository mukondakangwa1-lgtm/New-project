"""kudos chat archive, media, tool registry, visits

Revision ID: c0a1b2d3e4f5
Revises: f1a2b3c4d5e6
Create Date: 2026-08-10 15:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0a1b2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply this migration."""
    op.add_column('kudos_conversations', sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_kudos_conversations_archived', 'kudos_conversations', ['archived'])
    op.add_column('kudos_messages', sa.Column('media', sa.Text(), nullable=False, server_default=''))

    op.create_table(
        'kudos_tools',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('headers', sa.Text(), nullable=True),
        sa.Column('body_schema', sa.Text(), nullable=True),
        sa.Column('response_kind', sa.String(length=10), nullable=True),
        sa.Column('auth_type', sa.String(length=10), nullable=True),
        sa.Column('auth_value', sa.Text(), nullable=True),
        sa.Column('auth_header_name', sa.String(length=60), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_kudos_tools_name', 'kudos_tools', ['name'])

    op.create_table(
        'visits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('guest_key', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('ai_name', sa.String(length=60), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=300), nullable=True),
        sa.Column('path', sa.String(length=255), nullable=True),
        sa.Column('referrer', sa.String(length=300), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('visit_count', sa.Integer(), nullable=True),
    )
    op.create_index('ix_visits_guest_key', 'visits', ['guest_key'])
    op.create_index('ix_visits_user_id', 'visits', ['user_id'])

    op.create_table(
        'radio_places',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('place_id', sa.String(length=120), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('country', sa.String(length=120), nullable=True),
        sa.Column('continent', sa.String(length=60), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('live_station_count', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_radio_places_place_id', 'radio_places', ['place_id'])

    op.create_table(
        'radio_stations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('station_id', sa.String(length=160), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=True),
        sa.Column('place_name', sa.String(length=200), nullable=True),
        sa.Column('country', sa.String(length=120), nullable=True),
        sa.Column('stream_path', sa.String(length=255), nullable=True),
        sa.Column('genre', sa.String(length=200), nullable=True),
        sa.Column('current_track', sa.String(length=255), nullable=True),
        sa.Column('frequency', sa.String(length=30), nullable=True),
        sa.Column('is_live', sa.Boolean(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_radio_stations_station_id', 'radio_stations', ['station_id'])


def downgrade() -> None:
    """Revert this migration."""
    op.drop_index('ix_radio_stations_station_id', table_name='radio_stations')
    op.drop_table('radio_stations')
    op.drop_index('ix_radio_places_place_id', table_name='radio_places')
    op.drop_table('radio_places')
    op.drop_index('ix_visits_user_id', table_name='visits')
    op.drop_index('ix_visits_guest_key', table_name='visits')
    op.drop_table('visits')
    op.drop_index('ix_kudos_tools_name', table_name='kudos_tools')
    op.drop_table('kudos_tools')
    op.drop_column('kudos_messages', 'media')
    op.drop_index('ix_kudos_conversations_archived', table_name='kudos_conversations')
    op.drop_column('kudos_conversations', 'archived')
