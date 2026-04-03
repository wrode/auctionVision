"""add finn_forsale_listings table

Revision ID: e5a9f1b2c3d4
Revises: d4f8a2e91b03
Create Date: 2026-04-03 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a9f1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd4f8a2e91b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'finn_forsale_listings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('finn_id', sa.String(50), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('price_nok', sa.Float(), nullable=True),
        sa.Column('brand', sa.String(200), nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('search_query', sa.String(200), nullable=False),
        sa.Column('query_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('disappeared_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_forsale_finn_id', 'finn_forsale_listings', ['finn_id'], unique=False)
    op.create_index('idx_forsale_query', 'finn_forsale_listings', ['search_query', 'query_type'], unique=False)
    op.create_index('idx_forsale_status', 'finn_forsale_listings', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_forsale_status', table_name='finn_forsale_listings')
    op.drop_index('idx_forsale_query', table_name='finn_forsale_listings')
    op.drop_index('idx_forsale_finn_id', table_name='finn_forsale_listings')
    op.drop_table('finn_forsale_listings')
