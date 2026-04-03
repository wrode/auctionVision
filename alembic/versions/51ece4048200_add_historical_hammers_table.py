"""add historical_hammers table

Revision ID: 51ece4048200
Revises: a1b2c3d4e5f6
Create Date: 2026-04-02 19:49:31.799021

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51ece4048200'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('lot_scores', sa.Column('demand_score', sa.Float(), nullable=True))
    op.create_index('idx_scores_demand', 'lot_scores', ['demand_score'], unique=False)

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
    )
    op.create_index('ix_historical_hammers_external_lot_id', 'historical_hammers', ['external_lot_id'], unique=True)
    op.create_index('ix_historical_hammers_designer_name', 'historical_hammers', ['designer_name'])
    op.create_index('ix_historical_hammers_object_type', 'historical_hammers', ['object_type'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_historical_hammers_object_type', table_name='historical_hammers')
    op.drop_index('ix_historical_hammers_designer_name', table_name='historical_hammers')
    op.drop_index('ix_historical_hammers_external_lot_id', table_name='historical_hammers')
    op.drop_table('historical_hammers')
    op.drop_index('idx_scores_demand', table_name='lot_scores')
    op.drop_column('lot_scores', 'demand_score')
