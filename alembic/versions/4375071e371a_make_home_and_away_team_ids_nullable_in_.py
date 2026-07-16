"""make home and away team ids nullable in fixtures

Revision ID: 4375071e371a
Revises: 7fa565bb1f2c
Create Date: 2026-06-30 13:03:59.695227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4375071e371a'
down_revision: Union[str, Sequence[str], None] = '7fa565bb1f2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make home_team_id and away_team_id nullable on Postgres and SQLite
    with op.batch_alter_table('fixtures') as batch_op:
        batch_op.alter_column('home_team_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('away_team_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Make home_team_id and away_team_id not nullable (if reverting)
    with op.batch_alter_table('fixtures') as batch_op:
        batch_op.alter_column('home_team_id', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('away_team_id', existing_type=sa.Integer(), nullable=False)

