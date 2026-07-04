"""fix workers permissions

Revision ID: a8f92d03e4e4
Revises: 94b63b8461aa
Create Date: 2026-07-04 16:07:32.671576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f92d03e4e4'
down_revision: Union[str, None] = '94b63b8461aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())