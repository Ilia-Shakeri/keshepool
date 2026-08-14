"""add opaque one-time referral codes

Revision ID: 013
Revises: 012
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REFERRAL_CODE_DEFAULT = sa.text("replace(gen_random_uuid()::text, '-', '')")
_PROTECT_REFERRER_FUNCTION_SQL = """
CREATE FUNCTION keshepool_protect_user_referrer_id()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.referrer_id IS NOT NULL
       AND NEW.referrer_id IS DISTINCT FROM OLD.referrer_id THEN
        RAISE EXCEPTION 'user referrer attribution is immutable';
    END IF;
    RETURN NEW;
END;
$$
"""
_PROTECT_REFERRER_TRIGGER_SQL = """
CREATE TRIGGER trg_users_protect_referrer_id
BEFORE UPDATE OF referrer_id ON users
FOR EACH ROW
EXECUTE FUNCTION keshepool_protect_user_referrer_id()
"""


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "referral_code",
            sa.String(length=32),
            nullable=False,
            server_default=_REFERRAL_CODE_DEFAULT,
        ),
    )
    op.create_unique_constraint(
        "uq_users_referral_code",
        "users",
        ["referral_code"],
    )
    op.create_check_constraint(
        "ck_users_referral_code_format",
        "users",
        "referral_code ~ '^[0-9a-f]{32}$'",
    )
    op.create_check_constraint(
        "ck_users_no_self_referral",
        "users",
        "referrer_id IS NULL OR referrer_id <> id",
    )
    op.execute(_PROTECT_REFERRER_FUNCTION_SQL)
    op.execute(_PROTECT_REFERRER_TRIGGER_SQL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_users_protect_referrer_id ON users")
    op.execute("DROP FUNCTION IF EXISTS keshepool_protect_user_referrer_id()")
    op.drop_constraint("ck_users_no_self_referral", "users", type_="check")
    op.drop_constraint("ck_users_referral_code_format", "users", type_="check")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referral_code")
