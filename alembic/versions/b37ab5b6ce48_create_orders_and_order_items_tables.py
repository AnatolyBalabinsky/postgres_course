"""create orders and order_items tables

Revision ID: b37ab5b6ce48
Revises: 3482accca3b4
Create Date: 2026-06-10 22:34:49.236041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b37ab5b6ce48'
down_revision: Union[str, None] = '3482accca3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())