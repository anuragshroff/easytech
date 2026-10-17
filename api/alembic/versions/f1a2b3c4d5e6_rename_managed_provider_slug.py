"""rename managed provider slug from dograh to easytech

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-10-15 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ponytail: only rewrites rows that actually used the managed provider; a
# fresh install (backfills now write "easytech") is a no-op. Add a per-column
# transform only if a non-managed "dograh" value ever appears.
def upgrade() -> None:
    op.execute(
        "UPDATE provider_connections SET provider = 'easytech' "
        "WHERE provider = 'dograh'"
    )
    op.execute(
        "UPDATE provider_connections SET name = 'EasyTech' WHERE name = 'Dograh'"
    )
    op.execute(
        """
        UPDATE organization_configurations
        SET value = (
            (value::jsonb - 'dograh')
            || jsonb_build_object('mode', 'easytech', 'easytech', value::jsonb -> 'dograh')
        )::json
        WHERE value::jsonb ->> 'mode' = 'dograh'
          AND value::jsonb ? 'dograh'
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE provider_connections SET provider = 'dograh' "
        "WHERE provider = 'easytech'"
    )
    op.execute(
        "UPDATE provider_connections SET name = 'Dograh' WHERE name = 'EasyTech'"
    )
    op.execute(
        """
        UPDATE organization_configurations
        SET value = (
            (value::jsonb - 'easytech')
            || jsonb_build_object('mode', 'dograh', 'dograh', value::jsonb -> 'easytech')
        )::json
        WHERE value::jsonb ->> 'mode' = 'easytech'
          AND value::jsonb ? 'easytech'
        """
    )
