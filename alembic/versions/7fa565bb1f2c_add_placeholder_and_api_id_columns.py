"""add placeholder and api_id columns

Revision ID: 7fa565bb1f2c
Revises: 766d253ea2b0
Create Date: 2026-06-30 12:45:47.425678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fa565bb1f2c'
down_revision: Union[str, Sequence[str], None] = '766d253ea2b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to fixtures table
    op.add_column('fixtures', sa.Column('home_team_placeholder', sa.String(), nullable=True))
    op.add_column('fixtures', sa.Column('away_team_placeholder', sa.String(), nullable=True))
    op.add_column('fixtures', sa.Column('api_id', sa.String(), nullable=True))
    # Add unique constraint index on api_id
    op.create_index(op.f('ix_fixtures_api_id'), 'fixtures', ['api_id'], unique=True)


def downgrade() -> None:
    # Drop columns and index
    op.drop_index(op.f('ix_fixtures_api_id'), table_name='fixtures')
    op.drop_column('fixtures', 'api_id')
    op.drop_column('fixtures', 'away_team_placeholder')
    op.drop_column('fixtures', 'home_team_placeholder')
