"""add processed_by and inventory_manager sales permissions

Revision ID: 5ac585c5deaf
Revises: 1084180d9c94
Create Date: 2026-07-06 22:04:16.482092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ac585c5deaf'
down_revision: Union[str, None] = '1084180d9c94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())