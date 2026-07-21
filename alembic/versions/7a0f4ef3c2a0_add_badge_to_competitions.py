"""add_badge_to_competitions

Revision ID: 7a0f4ef3c2a0
Revises: 4bb60ab74106
Create Date: 2026-07-21 13:46:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7a0f4ef3c2a0'
down_revision: Union[str, Sequence[str], None] = 'a9977e5eafbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('competitions')]
    if 'badge' not in columns:
        with op.batch_alter_table('competitions', schema=None) as batch_op:
            batch_op.add_column(sa.Column('badge', sa.String(), nullable=True, server_default='⚽'))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('competitions')]
    if 'badge' in columns:
        with op.batch_alter_table('competitions', schema=None) as batch_op:
            batch_op.drop_column('badge')
