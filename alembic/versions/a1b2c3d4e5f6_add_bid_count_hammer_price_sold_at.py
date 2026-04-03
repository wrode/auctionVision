"""add bid_count, hammer_price, sold_at to parsed_lot_fields

Revision ID: a1b2c3d4e5f6
Revises: dfbe300bcf75
Create Date: 2026-04-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'dfbe300bcf75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('parsed_lot_fields', sa.Column('bid_count', sa.Integer(), nullable=True))
    op.add_column('parsed_lot_fields', sa.Column('hammer_price', sa.Float(), nullable=True))
    op.add_column('parsed_lot_fields', sa.Column('sold_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('parsed_lot_fields', 'sold_at')
    op.drop_column('parsed_lot_fields', 'hammer_price')
    op.drop_column('parsed_lot_fields', 'bid_count')
