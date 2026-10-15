"""add organization_invitations

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-15 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'member'"),
        ),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_organization_invitations_id"),
        "organization_invitations",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_invitations_org",
        "organization_invitations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_invitations_email_lower",
        "organization_invitations",
        [sa.text("lower(email)")],
        unique=False,
    )
    op.create_index(
        "ix_organization_invitations_token_hash",
        "organization_invitations",
        ["token_hash"],
        unique=True,
    )
    # One pending invitation per (org, email); accepted rows are kept.
    op.create_index(
        "uq_organization_invitations_pending",
        "organization_invitations",
        ["organization_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_organization_invitations_pending",
        table_name="organization_invitations",
    )
    op.drop_index(
        "ix_organization_invitations_token_hash",
        table_name="organization_invitations",
    )
    op.drop_index(
        "ix_organization_invitations_email_lower",
        table_name="organization_invitations",
    )
    op.drop_index(
        "ix_organization_invitations_org",
        table_name="organization_invitations",
    )
    op.drop_index(
        op.f("ix_organization_invitations_id"),
        table_name="organization_invitations",
    )
    op.drop_table("organization_invitations")
