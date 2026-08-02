"""add durable admin authorization controls

Revision ID: 008
Revises: 007
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_break_glass", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("char_length(telegram_id) BETWEEN 1 AND 20", name="ck_admin_identity_telegram_id_length"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_table(
        "admin_role_grants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_identity_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("granted_by_telegram_id", sa.String(length=20), nullable=False),
        sa.Column("revoked_by_telegram_id", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('superadmin', 'finance', 'catalog', 'support', 'auditor')", name="ck_admin_role_grant_role"),
        sa.ForeignKeyConstraint(["admin_identity_id"], ["admin_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_admin_role_grant_active",
        "admin_role_grants",
        ["admin_identity_id", "role"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "admin_action_nonces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nonce_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_telegram_id", sa.String(length=20), nullable=False),
        sa.Column("chat_id", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=180), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nonce_hash", name="uq_admin_action_nonce_hash"),
    )
    op.create_index("ix_admin_action_nonce_expiry", "admin_action_nonces", ["expires_at"])
    op.create_table(
        "admin_approval_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=180), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_by_telegram_id", sa.String(length=20), nullable=False),
        sa.Column("required_approvals", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("required_approvals >= 2", name="ck_admin_approval_required_count"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'executed', 'expired', 'cancelled')", name="ck_admin_approval_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_approval_pending", "admin_approval_requests", ["status", "expires_at", "id"])
    op.create_table(
        "admin_approval_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("approval_request_id", sa.Integer(), nullable=False),
        sa.Column("actor_telegram_id", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["approval_request_id"], ["admin_approval_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id", "actor_telegram_id", name="uq_admin_approval_actor"),
    )


def downgrade() -> None:
    op.drop_table("admin_approval_votes")
    op.drop_index("ix_admin_approval_pending", table_name="admin_approval_requests")
    op.drop_table("admin_approval_requests")
    op.drop_index("ix_admin_action_nonce_expiry", table_name="admin_action_nonces")
    op.drop_table("admin_action_nonces")
    op.drop_index("uq_admin_role_grant_active", table_name="admin_role_grants")
    op.drop_table("admin_role_grants")
    op.drop_table("admin_identities")
