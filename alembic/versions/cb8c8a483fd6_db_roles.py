"""db roles

Revision ID: cb8c8a483fd6
Revises: b37ab5b6ce48
Create Date: 2026-06-21 14:08:48.834922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb8c8a483fd6'
down_revision: Union[str, None] = 'b37ab5b6ce48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())