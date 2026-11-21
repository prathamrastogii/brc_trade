"""Create trades, positions, and prices tables.

Revision ID: 0002_trades_positions_prices
Revises: 0001_phase1_baseline
Create Date: 2026-11-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Keep <= 32 chars (alembic_version.version_num is VARCHAR(32)).
revision: str = "0002_trades_positions_prices"
down_revision: Union[str, None] = "0001_phase1_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("venue", sa.Text(), nullable=False),
        sa.Column("trade_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("traded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_trades_side"),
        sa.CheckConstraint("quantity > 0", name="ck_trades_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_trades_price_positive"),
        sa.PrimaryKeyConstraint("venue", "trade_id", name="pk_trades"),
    )

    op.create_table(
        "positions",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_cost", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_positions_quantity_nonnegative"),
        sa.CheckConstraint("avg_cost >= 0", name="ck_positions_avg_cost_nonnegative"),
        sa.PrimaryKeyConstraint("symbol"),
    )

    op.create_table(
        "prices",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("price > 0", name="ck_prices_price_positive"),
        sa.PrimaryKeyConstraint("symbol"),
    )


def downgrade() -> None:
    op.drop_table("prices")
    op.drop_table("positions")
    op.drop_table("trades")
