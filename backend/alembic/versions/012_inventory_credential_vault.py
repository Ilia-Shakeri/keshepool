"""add the additive inventory credential vault envelope

Revision ID: 012
Revises: 011
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("credential_ciphertext", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_nonce", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_key_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_envelope_version", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_fingerprint", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_masked_preview", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_canonical_length", sa.Integer(), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column(
            "credential_vault_state",
            sa.String(length=16),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_quarantine_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_vault_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_vault_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("credential_legacy_erased_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_inventory_credential_vault_state",
        "inventory_items",
        "credential_vault_state IN ('legacy', 'encrypted', 'quarantined')",
    )
    op.create_check_constraint(
        "ck_inventory_credential_fingerprint_length",
        "inventory_items",
        "credential_fingerprint IS NULL "
        "OR octet_length(credential_fingerprint) = 32",
    )
    op.create_check_constraint(
        "ck_inventory_credential_encrypted_bundle",
        "inventory_items",
        "credential_vault_state != 'encrypted' OR ("
        "credential_ciphertext IS NOT NULL "
        "AND octet_length(credential_ciphertext) >= 17 "
        "AND credential_nonce IS NOT NULL "
        "AND octet_length(credential_nonce) = 12 "
        "AND credential_key_version IS NOT NULL "
        "AND credential_key_version ~ '^[A-Za-z0-9._-]{1,32}$' "
        "AND credential_envelope_version = 1 "
        "AND credential_fingerprint IS NOT NULL "
        "AND octet_length(credential_fingerprint) = 32 "
        "AND credential_masked_preview IS NOT NULL "
        "AND credential_masked_preview = repeat(chr(8226), 8) "
        "AND credential_canonical_length BETWEEN 1 AND 16384 "
        "AND credential_vault_updated_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_inventory_credential_quarantine_reason",
        "inventory_items",
        "(credential_vault_state = 'quarantined') = "
        "(credential_quarantine_reason IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_inventory_credential_quarantine_reason_value",
        "inventory_items",
        "credential_quarantine_reason IS NULL OR "
        "credential_quarantine_reason IN ("
        "'invalid_legacy_value', 'duplicate_fingerprint', "
        "'integrity_verification_failed')",
    )
    op.create_check_constraint(
        "ck_inventory_credential_verified_state",
        "inventory_items",
        "credential_vault_verified_at IS NULL "
        "OR (credential_vault_state = 'encrypted' "
        "AND credential_vault_updated_at IS NOT NULL "
        "AND credential_vault_verified_at >= credential_vault_updated_at)",
    )
    op.create_check_constraint(
        "ck_inventory_credential_legacy_erasure",
        "inventory_items",
        "credential_legacy_erased_at IS NULL OR ("
        "credential_vault_state IN ('encrypted', 'quarantined'))",
    )
    op.create_check_constraint(
        "ck_inventory_credential_legacy_tombstone",
        "inventory_items",
        "credential_legacy_erased_at IS NULL "
        "OR credentials = 'vaulted:' || id::text",
    )
    op.create_index(
        "ix_inventory_vault_state_id",
        "inventory_items",
        ["credential_vault_state", "id"],
    )
    op.create_index(
        "uq_inventory_credential_fingerprint",
        "inventory_items",
        ["credential_fingerprint"],
        unique=True,
        postgresql_where=sa.text(
            "credential_fingerprint IS NOT NULL "
            "AND credential_vault_state = 'encrypted'"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_inventory_credential_fingerprint", table_name="inventory_items")
    op.drop_index("ix_inventory_vault_state_id", table_name="inventory_items")
    op.drop_constraint(
        "ck_inventory_credential_legacy_tombstone",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_legacy_erasure",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_verified_state",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_quarantine_reason",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_quarantine_reason_value",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_encrypted_bundle",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_vault_state",
        "inventory_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_inventory_credential_fingerprint_length",
        "inventory_items",
        type_="check",
    )
    op.drop_column("inventory_items", "credential_legacy_erased_at")
    op.drop_column("inventory_items", "credential_vault_verified_at")
    op.drop_column("inventory_items", "credential_vault_updated_at")
    op.drop_column("inventory_items", "credential_quarantine_reason")
    op.drop_column("inventory_items", "credential_vault_state")
    op.drop_column("inventory_items", "credential_canonical_length")
    op.drop_column("inventory_items", "credential_masked_preview")
    op.drop_column("inventory_items", "credential_fingerprint")
    op.drop_column("inventory_items", "credential_envelope_version")
    op.drop_column("inventory_items", "credential_key_version")
    op.drop_column("inventory_items", "credential_nonce")
    op.drop_column("inventory_items", "credential_ciphertext")
