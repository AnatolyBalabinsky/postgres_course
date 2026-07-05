"""add cities table and update warehouses

Revision ID: 802f2e7d81b1
Revises: 7917620d039b
Create Date: 2026-07-04 13:35:56.367347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '802f2e7d81b1'
down_revision: Union[str, None] = '7917620d039b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())