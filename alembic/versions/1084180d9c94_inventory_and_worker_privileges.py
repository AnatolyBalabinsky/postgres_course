"""inventory and worker privileges

Revision ID: 1084180d9c94
Revises: 1212b894954e
Create Date: 2026-07-04 14:33:28.775578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1084180d9c94'
down_revision: Union[str, None] = '1212b894954e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())