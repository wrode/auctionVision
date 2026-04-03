"""add finn_market_data table

Revision ID: d4f8a2e91b03
Revises: c70be7ba83cb
Create Date: 2026-04-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f8a2e91b03'
down_revision: Union[str, Sequence[str], None] = 'c70be7ba83cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'finn_market_data',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('query_type', sa.String(50), nullable=False),
        sa.Column('query_value', sa.String(200), nullable=False),
        sa.Column('finn_category', sa.String(200), nullable=True),
        sa.Column('listing_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_price_nok', sa.Float(), nullable=True),
        sa.Column('median_price_nok', sa.Float(), nullable=True),
        sa.Column('min_price_nok', sa.Float(), nullable=True),
        sa.Column('max_price_nok', sa.Float(), nullable=True),
        sa.Column('price_samples', sa.JSON(), nullable=True),
        sa.Column('sample_listings', sa.JSON(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_finn_market_query', 'finn_market_data', ['query_type', 'query_value'], unique=False)
    op.create_index('idx_finn_market_scraped', 'finn_market_data', ['scraped_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_finn_market_scraped', table_name='finn_market_data')
    op.drop_index('idx_finn_market_query', table_name='finn_market_data')
    op.drop_table('finn_market_data')
