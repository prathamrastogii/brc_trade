from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Table,
    Text,
    func,
    text,
)

metadata = MetaData()

trades = Table(
    "trades",
    metadata,
    Column("venue", Text, nullable=False),
    Column("trade_id", Text, nullable=False),
    Column("symbol", Text, nullable=False),
    Column("side", Text, nullable=False),
    Column("quantity", Numeric, nullable=False),
    Column("price", Numeric, nullable=False),
    Column("traded_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("venue", "trade_id", name="pk_trades"),
    CheckConstraint("side IN ('BUY', 'SELL')", name="ck_trades_side"),
    CheckConstraint("quantity > 0", name="ck_trades_quantity_positive"),
    CheckConstraint("price > 0", name="ck_trades_price_positive"),
)

positions = Table(
    "positions",
    metadata,
    Column("symbol", Text, primary_key=True),
    Column("quantity", Numeric, nullable=False, server_default=text("0")),
    Column("avg_cost", Numeric, nullable=False, server_default=text("0")),
    Column("realized_pnl", Numeric, nullable=False, server_default=text("0")),
    CheckConstraint("quantity >= 0", name="ck_positions_quantity_nonnegative"),
    CheckConstraint("avg_cost >= 0", name="ck_positions_avg_cost_nonnegative"),
)

prices = Table(
    "prices",
    metadata,
    Column("symbol", Text, primary_key=True),
    Column("price", Numeric, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("price > 0", name="ck_prices_price_positive"),
)
