"""add currency and gateway to transactions; add cashout_requests table

Revision ID: 002
Revises: 001
Create Date: 2026-06-27

All DDL in upgrade() uses IF NOT EXISTS / DO-EXCEPTION guards so the
migration is safe to re-run after a partial failure.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── transactions.currency ─────────────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS currency VARCHAR(10)"
    ))
    conn.execute(sa.text(
        "UPDATE transactions SET currency = 'IRR' WHERE currency IS NULL"
    ))
    # SET NOT NULL is idempotent in PostgreSQL — safe if already applied
    conn.execute(sa.text(
        "ALTER TABLE transactions ALTER COLUMN currency SET NOT NULL"
    ))

    # ── transactions.gateway ──────────────────────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS gateway VARCHAR(50)"
    ))

    # ── cashoutrequeststatus enum ─────────────────────────────────────────────
    # DO block swallows duplicate_object so re-runs are safe
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE cashoutrequeststatus AS ENUM ('pending', 'reviewed', 'completed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    # ── cashout_requests table ────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cashout_requests (
            id          SERIAL                   NOT NULL,
            user_id     INTEGER                  NOT NULL REFERENCES users(id),
            source_platform VARCHAR(100)         NOT NULL,
            custom_source   VARCHAR(200),
            details_text    TEXT                 NOT NULL,
            status      cashoutrequeststatus      NOT NULL,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at  TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (id)
        )
    """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cashout_requests_id "
        "ON cashout_requests (id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cashout_requests_user_id "
        "ON cashout_requests (user_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cashout_requests_status "
        "ON cashout_requests (status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cashout_requests_user_created "
        "ON cashout_requests (user_id, created_at)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_cashout_requests_user_created"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_cashout_requests_status"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_cashout_requests_user_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_cashout_requests_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS cashout_requests"))
    conn.execute(sa.text("DROP TYPE IF EXISTS cashoutrequeststatus"))
    conn.execute(sa.text("ALTER TABLE transactions DROP COLUMN IF EXISTS gateway"))
    conn.execute(sa.text("ALTER TABLE transactions DROP COLUMN IF EXISTS currency"))
