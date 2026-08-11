"""KUDOS internal world map — offline navigation + facts

Seeded places KUDOS can reason about and navigate with even fully offline
(countries, capitals, major cities, landmarks). No coordinate is ever guessed:
lat/lon are authoritative public values or NULL when genuinely unknown.

Revision ID: 
Revises: f3a4b5c6d7e8
Create Date: 2026-08-11 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kudos_map_places",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("region", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("continent", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("place_type", sa.String(length=30), nullable=False, server_default="city"),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("aliases", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("search_text", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kudos_map_places_name", "kudos_map_places", ["name"])

    op.create_table(
        "kudos_access_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bssid", sa.String(length=32), nullable=False, unique=True),
        sa.Column("ssid", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("lat", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lon", sa.Float(), nullable=False, server_default="0"),
        sa.Column("accuracy_m", sa.Float(), nullable=False, server_default="120"),
        sa.Column("last_signal_dbm", sa.Integer(), nullable=False, server_default="-70"),
        sa.Column("observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "kudos_cell_towers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cell_key", sa.String(length=80), nullable=False, unique=True),
        sa.Column("mcc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mnc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lac", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lat", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lon", sa.Float(), nullable=False, server_default="0"),
        sa.Column("accuracy_m", sa.Float(), nullable=False, server_default="1500"),
        sa.Column("observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "kudos_scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("kudos_devices.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("gps_lat", sa.Float(), nullable=True),
        sa.Column("gps_lon", sa.Float(), nullable=True),
        sa.Column("gps_accuracy_m", sa.Float(), nullable=True),
        sa.Column("wifi_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cells_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("kudos_scans")
    op.drop_table("kudos_cell_towers")
    op.drop_table("kudos_access_points")
    op.drop_index("ix_kudos_map_places_name", table_name="kudos_map_places")
    op.drop_table("kudos_map_places")