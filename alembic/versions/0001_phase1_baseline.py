"""Phase 1 baseline (empty schema; tables land in Phase 2).

Revision ID: 0001_phase1_baseline
Revises:
Create Date: 2026-11-21

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_phase1_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Placeholder so `alembic upgrade head` succeeds on empty DB.
    # Real tables (trades, positions, prices) are added in Phase 2.
    pass


def downgrade() -> None:
    pass
