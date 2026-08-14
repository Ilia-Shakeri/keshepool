"""add structured admin audit context

Revision ID: 010
Revises: 009
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_audit_logs", sa.Column("outcome", sa.String(length=16), nullable=False, server_default="success"))
    op.add_column("admin_audit_logs", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("admin_audit_logs", sa.Column("update_id", sa.BigInteger(), nullable=True))
    op.add_column("admin_audit_logs", sa.Column("chat_id", sa.String(length=24), nullable=True))
    op.add_column("admin_audit_logs", sa.Column("reason", sa.String(length=100), nullable=True))
    op.add_column("admin_audit_logs", sa.Column("old_values", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("admin_audit_logs", sa.Column("new_values", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.create_check_constraint(
        "ck_admin_audit_outcome",
        "admin_audit_logs",
        "outcome IN ('success', 'rejected', 'failed', 'requested')",
    )
    op.create_index("ix_admin_audit_outcome_created", "admin_audit_logs", ["outcome", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_outcome_created", table_name="admin_audit_logs")
    op.drop_constraint("ck_admin_audit_outcome", "admin_audit_logs", type_="check")
    op.drop_column("admin_audit_logs", "new_values")
    op.drop_column("admin_audit_logs", "old_values")
    op.drop_column("admin_audit_logs", "reason")
    op.drop_column("admin_audit_logs", "chat_id")
    op.drop_column("admin_audit_logs", "update_id")
    op.drop_column("admin_audit_logs", "request_id")
    op.drop_column("admin_audit_logs", "outcome")
