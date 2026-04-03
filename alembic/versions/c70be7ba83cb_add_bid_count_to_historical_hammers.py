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
    from sqlalchemy import inspect
    bind = op.get_bind()
    if 'historical_hammers' not in inspect(bind).get_table_names():
        op.create_table(
            'historical_hammers',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('external_lot_id', sa.String(200), unique=True, nullable=False),
            sa.Column('lot_url', sa.String(500), nullable=False),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category_raw', sa.String(200), nullable=True),
            sa.Column('designer_name', sa.String(200), nullable=True),
            sa.Column('object_type', sa.String(100), nullable=True),
            sa.Column('materials', sa.JSON(), nullable=True),
            sa.Column('hammer_price', sa.Float(), nullable=True),
            sa.Column('estimate_low', sa.Float(), nullable=True),
            sa.Column('estimate_high', sa.Float(), nullable=True),
            sa.Column('currency', sa.String(10), default='EUR'),
            sa.Column('auction_house_name', sa.String(200), nullable=True),
            sa.Column('seller_location', sa.String(200), nullable=True),
            sa.Column('auction_end_date', sa.DateTime(), nullable=True),
            sa.Column('was_sold', sa.Integer(), default=1),
            sa.Column('bid_count', sa.Integer(), nullable=True),
        )
        op.create_index('ix_historical_hammers_external_lot_id', 'historical_hammers', ['external_lot_id'], unique=True)
        op.create_index('ix_historical_hammers_designer_name', 'historical_hammers', ['designer_name'])
        op.create_index('ix_historical_hammers_object_type', 'historical_hammers', ['object_type'])
    else:
        op.add_column('historical_hammers', sa.Column('bid_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('historical_hammers', 'bid_count')
