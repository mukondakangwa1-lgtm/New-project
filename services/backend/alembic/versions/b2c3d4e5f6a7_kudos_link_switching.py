"""KUDOS link switching — terrestrial <-> satellite (Starlink / Android NTN)

Devices report the transports they can actually see (Wi-Fi, cellular,
satellite); KUDOS records the measured link and how to switch between them.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-11 09:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kudos_network_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("kudos_devices.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("primary_transport", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("transports", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("signal_dbm", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metered", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("constrained", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("satellite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("satellite_backhaul", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("bandwidth_kbps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rtt_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("reported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kudos_network_states_device_id", "kudos_network_states", ["device_id"])
    op.create_index("ix_kudos_network_states_user_id", "kudos_network_states", ["user_id"])

    op.create_table(
        "kudos_network_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("kudos_devices.id"), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("reason", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kudos_network_settings_device_id", "kudos_network_settings", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_kudos_network_settings_device_id", table_name="kudos_network_settings")
    op.drop_table("kudos_network_settings")
    op.drop_index("ix_kudos_network_states_user_id", table_name="kudos_network_states")
    op.drop_index("ix_kudos_network_states_device_id", table_name="kudos_network_states")
    op.drop_table("kudos_network_states")