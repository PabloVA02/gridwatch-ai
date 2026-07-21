"""Create energy readings table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "energy_readings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=80), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("energy_kwh", sa.Float(), nullable=False),
        sa.Column("voltage", sa.Float(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "observed_at", name="uq_reading_device_time"),
    )
    op.create_index("ix_energy_readings_device_id", "energy_readings", ["device_id"])
    op.create_index("ix_reading_device_time", "energy_readings", ["device_id", "observed_at"])


def downgrade() -> None:
    op.drop_index("ix_reading_device_time", table_name="energy_readings")
    op.drop_index("ix_energy_readings_device_id", table_name="energy_readings")
    op.drop_table("energy_readings")
