"""add bid_count to historical_hammers

Revision ID: c70be7ba83cb
Revises: 51ece4048200
Create Date: 2026-04-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c70be7ba83cb'
down_revision: Union[str, Sequence[str], None] = '51ece4048200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('historical_hammers', sa.Column('bid_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('historical_hammers', 'bid_count')
