"""add wallet billing ledger

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("rate_cents_per_minute", sa.Integer(), nullable=True),
        sa.Column("minimum_balance_cents", sa.Integer(), nullable=True),
        sa.Column("enforce_pre_call_balance", sa.Boolean(), nullable=True),
        sa.Column("auto_recharge_enabled", sa.Boolean(), nullable=True),
        sa.Column("auto_recharge_threshold_cents", sa.Integer(), nullable=True),
        sa.Column("auto_recharge_amount_cents", sa.Integer(), nullable=True),
        sa.Column("payment_links", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_billing_settings_id"), "billing_settings", ["id"], unique=False
    )
    op.create_index(
        "uq_billing_settings_platform",
        "billing_settings",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NULL"),
    )
    op.create_index(
        "uq_billing_settings_org",
        "billing_settings",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )

    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=8),
            nullable=False,
            server_default=sa.text("'usd'"),
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("external_ref", sa.String(), nullable=True),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"], ["workflow_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_wallet_transactions_id"),
        "wallet_transactions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_transactions_org_created",
        "wallet_transactions",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_wallet_transactions_external_ref",
        "wallet_transactions",
        ["source", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    op.create_index(
        "uq_wallet_transactions_usage_run",
        "wallet_transactions",
        ["workflow_run_id"],
        unique=True,
        postgresql_where=sa.text("workflow_run_id IS NOT NULL"),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=False),
        sa.Column(
            "duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("rate_cents_per_minute", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"], ["workflow_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_run_id", name="uq_usage_records_workflow_run"),
    )
    op.create_index(op.f("ix_usage_records_id"), "usage_records", ["id"], unique=False)
    op.create_index(
        "ix_usage_records_org_created",
        "usage_records",
        ["organization_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_usage_records_org_created", table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_id"), table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index(
        "uq_wallet_transactions_usage_run", table_name="wallet_transactions"
    )
    op.drop_index(
        "uq_wallet_transactions_external_ref", table_name="wallet_transactions"
    )
    op.drop_index(
        "ix_wallet_transactions_org_created", table_name="wallet_transactions"
    )
    op.drop_index(
        op.f("ix_wallet_transactions_id"), table_name="wallet_transactions"
    )
    op.drop_table("wallet_transactions")
    op.drop_index("uq_billing_settings_org", table_name="billing_settings")
    op.drop_index("uq_billing_settings_platform", table_name="billing_settings")
    op.drop_index(op.f("ix_billing_settings_id"), table_name="billing_settings")
    op.drop_table("billing_settings")
