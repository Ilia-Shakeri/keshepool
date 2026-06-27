"""add features column to products

Revision ID: 003
Revises: 002
Create Date: 2026-06-27

Idempotent: uses IF NOT EXISTS so it is safe to re-run after a partial failure.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE products ADD COLUMN IF NOT EXISTS features TEXT"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE products DROP COLUMN IF EXISTS features"))
