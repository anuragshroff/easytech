"""rename dograh token columns to easytech

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-10-15 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "organizations",
        "quota_dograh_tokens",
        new_column_name="quota_easytech_tokens",
    )
    op.alter_column(
        "organization_usage_cycles",
        "quota_dograh_tokens",
        new_column_name="quota_easytech_tokens",
    )
    op.alter_column(
        "organization_usage_cycles",
        "used_dograh_tokens",
        new_column_name="used_easytech_tokens",
    )


def downgrade() -> None:
    op.alter_column(
        "organizations",
        "quota_easytech_tokens",
        new_column_name="quota_dograh_tokens",
    )
    op.alter_column(
        "organization_usage_cycles",
        "quota_easytech_tokens",
        new_column_name="quota_dograh_tokens",
    )
    op.alter_column(
        "organization_usage_cycles",
        "used_easytech_tokens",
        new_column_name="used_dograh_tokens",
    )
