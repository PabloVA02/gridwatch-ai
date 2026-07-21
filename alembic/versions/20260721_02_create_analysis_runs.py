"""Create analysis run audit records.

Revision ID: 20260721_02
Revises: 20260721_01
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_02"
down_revision: str | None = "20260721_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detector_name", sa.String(length=80), nullable=False),
        sa.Column("detector_version", sa.String(length=30), nullable=False),
        sa.Column("detector_parameters", sa.JSON(), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=50), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("contamination", sa.Float(), nullable=False),
        sa.Column("anomalies_found", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_runs_run_id", "analysis_runs", ["run_id"], unique=True)
    op.create_index("ix_analysis_runs_device_id", "analysis_runs", ["device_id"], unique=False)
    op.create_index(
        "ix_analysis_runs_dataset_fingerprint",
        "analysis_runs",
        ["dataset_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_dataset_fingerprint", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_device_id", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_run_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
