"""fix inventory_manager catalog permissions

Revision ID: 94b63b8461aa
Revises: 1084180d9c94
Create Date: 2026-07-04 14:52:00.351854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94b63b8461aa'
down_revision: Union[str, None] = '1084180d9c94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())