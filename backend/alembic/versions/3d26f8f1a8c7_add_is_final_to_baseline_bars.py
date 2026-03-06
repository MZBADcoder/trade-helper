"""add is_final to baseline bars

Revision ID: 3d26f8f1a8c7
Revises: 268e0e9f2257
Create Date: 2026-03-06 05:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3d26f8f1a8c7"
down_revision: str | None = "268e0e9f2257"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_bars_day",
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "market_bars_minute",
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # Existing same-day rows may have been captured before the bar closed; force them
    # back through the refresh path after deployment.
    op.execute(
        """
        UPDATE market_bars_day
        SET is_final = false
        WHERE trade_date = timezone('America/New_York', now())::date
        """
    )
    op.execute(
        """
        UPDATE market_bars_minute
        SET is_final = false
        WHERE trade_date = timezone('America/New_York', now())::date
        """
    )

    op.alter_column("market_bars_day", "is_final", server_default=None)
    op.alter_column("market_bars_minute", "is_final", server_default=None)


def downgrade() -> None:
    op.drop_column("market_bars_minute", "is_final")
    op.drop_column("market_bars_day", "is_final")
