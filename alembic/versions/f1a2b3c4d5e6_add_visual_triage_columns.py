"""add visual triage columns to lots

Revision ID: f1a2b3c4d5e6
Revises: e5a9f1b2c3d4
Create Date: 2026-04-03 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5a9f1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lots', sa.Column('visual_triage_result', sa.String(10), nullable=True))
    op.add_column('lots', sa.Column('visual_triage_reason', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('lots', 'visual_triage_reason')
    op.drop_column('lots', 'visual_triage_result')
