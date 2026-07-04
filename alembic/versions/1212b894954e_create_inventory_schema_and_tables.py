"""create inventory schema and tables

Revision ID: 1212b894954e
Revises: 7097f11a5b34
Create Date: 2026-07-04 14:17:46.115442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1212b894954e'
down_revision: Union[str, None] = '7097f11a5b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with open(f"alembic/sql/{revision}/up.sql") as file:
        op.execute(file.read())


def downgrade() -> None:
    with open(f"alembic/sql/{revision}/down.sql") as file:
        op.execute(file.read())