import enum
import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """Store enum values in PostgreSQL so Python enums match existing database labels."""
    return [member.value for member in enum_class]


def postgres_enum(enum_class: type[enum.Enum], name: str) -> Enum:
    """Build a stable PostgreSQL enum that stores each member's public value."""
    return Enum(
        enum_class,
        values_callable=enum_values,
        name=name,
        validate_strings=True,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class ItemStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    ASSIGNED = "assigned"
    EXPIRED = "expired"
    DISABLED = "disabled"

class TransactionType(str, enum.Enum):
    DEPOSIT_IRR = "deposit_irr"
    DEPOSIT_CRYPTO = "deposit_crypto"
    PURCHASE = "purchase"
    CASHOUT = "cashout"
    REFUND = "refund"
    REFERRAL_BONUS = "referral_bonus"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

class OrderStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class CashoutRequestStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    COMPLETED = "completed"

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("referral_code", name="uq_users_referral_code"),
        CheckConstraint(
            "referral_code ~ '^[0-9a-f]{32}$'",
            name="ck_users_referral_code_format",
        ),
        CheckConstraint(
            "referrer_id IS NULL OR referrer_id <> id",
            name="ck_users_no_self_referral",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    is_premium = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, index=True, nullable=False)
    banned_at = Column(DateTime(timezone=True), nullable=True)
    banned_by = Column(String, nullable=True)
    role = Column(String, default="user", nullable=False)
    referral_code = Column(
        String(32),
        default=lambda: secrets.token_hex(16),
        server_default=text("replace(gen_random_uuid()::text, '-', '')"),
        nullable=False,
    )
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    cashout_requests = relationship("CashoutRequest", back_populates="user")
    referrer = relationship("User", remote_side=[id])

class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("user_id", name="uq_wallet_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    balance = Column(Numeric(precision=18, scale=2), default=0, nullable=False)

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")

class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_wallet_created", "wallet_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    amount = Column(Numeric(precision=24, scale=8), nullable=False)
    currency = Column(String(10), default="IRR", nullable=False)
    type = Column(postgres_enum(TransactionType, "transactiontype"), nullable=False)
    status = Column(
        postgres_enum(TransactionStatus, "transactionstatus"),
        default=TransactionStatus.PENDING,
        nullable=False,
    )
    gateway = Column(String(50), nullable=True)
    reference_id = Column(String, nullable=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    wallet = relationship("Wallet", back_populates="transactions")
    card_transfer_receipt = relationship(
        "CardTransferReceipt",
        back_populates="transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CardTransferReceipt(Base):
    __tablename__ = "card_transfer_receipts"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            name="uq_card_transfer_receipts_transaction_id",
        ),
        UniqueConstraint(
            "receipt_sha256",
            name="uq_card_transfer_receipts_sha256",
        ),
        CheckConstraint(
            "receipt_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_card_transfer_receipt_sha256",
        ),
        CheckConstraint(
            "octet_length(image_bytes) BETWEEN 1 AND 5000000",
            name="ck_card_transfer_receipt_size",
        ),
    )

    id = Column(Integer, primary_key=True)
    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_bytes = Column(LargeBinary, nullable=False)
    mime_type = Column(String(32), nullable=False, default="image/jpeg")
    receipt_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="card_transfer_receipt")
    deliveries = relationship(
        "CardTransferAdminDelivery",
        back_populates="receipt",
        cascade="all, delete-orphan",
    )


class CardTransferAdminDelivery(Base):
    __tablename__ = "card_transfer_admin_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "receipt_id",
            "chat_id",
            name="uq_card_transfer_delivery_receipt_chat",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_card_transfer_delivery_status",
        ),
        CheckConstraint(
            "attempts BETWEEN 0 AND 100",
            name="ck_card_transfer_delivery_attempts",
        ),
        Index(
            "ix_card_transfer_delivery_retry",
            "status",
            "next_attempt_at",
        ),
    )

    id = Column(Integer, primary_key=True)
    receipt_id = Column(
        Integer,
        ForeignKey("card_transfer_receipts.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_id = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    attempts = Column(SmallInteger, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    last_error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    receipt = relationship("CardTransferReceipt", back_populates="deliveries")

class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    icon = Column(String, default="Box", nullable=False)
    asset_url = Column(String, nullable=True)
    gradient = Column(String, default="from-gray-700 to-black", nullable=False)
    category = Column(String, default="tools", index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    features = Column(Text, nullable=True)  # JSON list of feature label strings shown in product modal
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")

class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "id",
            name="uq_product_variant_product_id_id",
        ),
    )

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True, nullable=False)
    duration = Column(String, nullable=False)
    price_label = Column(String, nullable=False)
    raw_price = Column(Numeric(precision=18, scale=2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    product = relationship("Product", back_populates="variants")
    inventory_items = relationship("InventoryItem", back_populates="variant")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        Index("ix_inventory_available", "product_id", "variant_id", "status"),
        Index(
            "ix_inventory_allocation_fifo",
            "product_id",
            "variant_id",
            "status",
            "expires_at",
            "created_at",
            "id",
        ),
        Index("ix_inventory_vault_state_id", "credential_vault_state", "id"),
        Index(
            "uq_inventory_credential_fingerprint",
            "credential_fingerprint",
            unique=True,
            postgresql_where=text(
                "credential_fingerprint IS NOT NULL "
                "AND credential_vault_state = 'encrypted'"
            ),
        ),
        UniqueConstraint("product_id", "variant_id", "credentials", name="uq_inventory_unique_credentials"),
        UniqueConstraint(
            "id",
            "product_id",
            "variant_id",
            name="uq_inventory_item_ownership",
        ),
        ForeignKeyConstraint(
            ["product_id", "variant_id"],
            ["product_variants.product_id", "product_variants.id"],
            name="fk_inventory_product_variant",
        ),
        CheckConstraint(
            "credential_vault_state IN ('legacy', 'encrypted', 'quarantined')",
            name="ck_inventory_credential_vault_state",
        ),
        CheckConstraint(
            "credential_fingerprint IS NULL "
            "OR octet_length(credential_fingerprint) = 32",
            name="ck_inventory_credential_fingerprint_length",
        ),
        CheckConstraint(
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
            name="ck_inventory_credential_encrypted_bundle",
        ),
        CheckConstraint(
            "(credential_vault_state = 'quarantined') = "
            "(credential_quarantine_reason IS NOT NULL)",
            name="ck_inventory_credential_quarantine_reason",
        ),
        CheckConstraint(
            "credential_quarantine_reason IS NULL OR "
            "credential_quarantine_reason IN ("
            "'invalid_legacy_value', 'duplicate_fingerprint', "
            "'integrity_verification_failed')",
            name="ck_inventory_credential_quarantine_reason_value",
        ),
        CheckConstraint(
            "credential_vault_verified_at IS NULL "
            "OR (credential_vault_state = 'encrypted' "
            "AND credential_vault_updated_at IS NOT NULL "
            "AND credential_vault_verified_at >= credential_vault_updated_at)",
            name="ck_inventory_credential_verified_state",
        ),
        CheckConstraint(
            "credential_legacy_erased_at IS NULL OR ("
            "credential_vault_state IN ('encrypted', 'quarantined'))",
            name="ck_inventory_credential_legacy_erasure",
        ),
        CheckConstraint(
            "credential_legacy_erased_at IS NULL "
            "OR credentials = 'vaulted:' || id::text",
            name="ck_inventory_credential_legacy_tombstone",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True, nullable=False)
    variant_id = Column(String, index=True, nullable=False)
    credentials = Column(Text, nullable=False)
    credential_ciphertext = Column(LargeBinary, nullable=True)
    credential_nonce = Column(LargeBinary, nullable=True)
    credential_key_version = Column(String(32), nullable=True)
    credential_envelope_version = Column(SmallInteger, nullable=True)
    credential_fingerprint = Column(LargeBinary, nullable=True)
    credential_masked_preview = Column(String(32), nullable=True)
    credential_canonical_length = Column(Integer, nullable=True)
    credential_vault_state = Column(
        String(16),
        default="legacy",
        server_default=text("'legacy'"),
        nullable=False,
    )
    credential_quarantine_reason = Column(String(64), nullable=True)
    credential_vault_updated_at = Column(DateTime(timezone=True), nullable=True)
    credential_vault_verified_at = Column(DateTime(timezone=True), nullable=True)
    credential_legacy_erased_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        postgres_enum(ItemStatus, "itemstatus"),
        default=ItemStatus.AVAILABLE,
        index=True,
        nullable=False,
    )
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    variant = relationship("ProductVariant", back_populates="inventory_items")

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("inventory_item_id", name="uq_order_inventory_item_id"),
        CheckConstraint(
            "credential_reveal_count BETWEEN 0 AND 100",
            name="ck_orders_credential_reveal_count",
        ),
        ForeignKeyConstraint(
            ["inventory_item_id", "product_id", "variant_id"],
            [
                "inventory_items.id",
                "inventory_items.product_id",
                "inventory_items.variant_id",
            ],
            name="fk_order_inventory_ownership",
        ),
        CheckConstraint(
            "(snapshot_state = 'complete' "
            "AND snapshot_quarantine_reason IS NULL "
            "AND product_title_snapshot IS NOT NULL "
            "AND char_length(product_title_snapshot) > 0 "
            "AND product_brand_snapshot IS NOT NULL "
            "AND char_length(product_brand_snapshot) > 0 "
            "AND variant_duration_snapshot IS NOT NULL "
            "AND char_length(variant_duration_snapshot) > 0 "
            "AND variant_price_label_snapshot IS NOT NULL "
            "AND char_length(variant_price_label_snapshot) > 0 "
            "AND currency_snapshot IS NOT NULL "
            "AND char_length(currency_snapshot) BETWEEN 3 AND 10 "
            "AND unit_price_amount IS NOT NULL AND unit_price_amount >= 0 "
            "AND tax_amount IS NOT NULL AND tax_amount >= 0 "
            "AND fee_amount IS NOT NULL AND fee_amount >= 0 "
            "AND total_amount_snapshot IS NOT NULL AND total_amount_snapshot >= 0 "
            "AND total_amount_snapshot = unit_price_amount + tax_amount + fee_amount "
            "AND total_amount = total_amount_snapshot) OR "
            "(snapshot_state = 'legacy_quarantined' "
            "AND snapshot_quarantine_reason IN ("
            "'historical_snapshot_unavailable', 'ownership_mismatch') "
            "AND (total_amount_snapshot IS NULL "
            "OR total_amount_snapshot = total_amount))",
            name="ck_order_commercial_snapshot",
        ),
        Index(
            "uq_orders_user_idempotency_key",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_orders_user_created_id", "user_id", "created_at", "id"),
        Index("ix_orders_snapshot_state_created", "snapshot_state", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    variant_id = Column(String, ForeignKey("product_variants.id"), nullable=False)
    inventory_item_id = Column(Integer, nullable=False)
    total_amount = Column(Numeric(precision=18, scale=2), nullable=False)
    product_title_snapshot = Column(String(180), nullable=True)
    product_brand_snapshot = Column(String(180), nullable=True)
    variant_duration_snapshot = Column(String(120), nullable=True)
    variant_price_label_snapshot = Column(String(50), nullable=True)
    currency_snapshot = Column(String(10), nullable=True)
    unit_price_amount = Column(Numeric(precision=18, scale=2), nullable=True)
    tax_amount = Column(Numeric(precision=18, scale=2), nullable=True)
    fee_amount = Column(Numeric(precision=18, scale=2), nullable=True)
    total_amount_snapshot = Column(Numeric(precision=18, scale=2), nullable=True)
    snapshot_state = Column(
        String(24),
        default="legacy_quarantined",
        server_default=text("'legacy_quarantined'"),
        nullable=False,
    )
    snapshot_quarantine_reason = Column(
        String(64),
        default="historical_snapshot_unavailable",
        server_default=text("'historical_snapshot_unavailable'"),
        nullable=True,
    )
    idempotency_key = Column(String(64), nullable=True)
    status = Column(
        postgres_enum(OrderStatus, "orderstatus"),
        default=OrderStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    credential_reveal_count = Column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )

    user = relationship("User", back_populates="orders")
    product = relationship("Product")
    variant = relationship("ProductVariant")
    inventory_item = relationship("InventoryItem", viewonly=True)


class CredentialRevealEvent(Base):
    __tablename__ = "credential_reveal_events"
    __table_args__ = (
        Index("ix_credential_reveal_order_created", "order_id", "created_at", "id"),
        Index("ix_credential_reveal_user_created", "user_id", "created_at", "id"),
        CheckConstraint(
            "outcome IN ('allowed', 'denied_not_found', 'denied_state', "
            "'denied_limit', 'denied_size', 'denied_vault')",
            name="ck_credential_reveal_event_outcome",
        ),
        CheckConstraint(
            "reveal_count IS NULL OR reveal_count BETWEEN 0 AND 100",
            name="ck_credential_reveal_event_count",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_telegram_id = Column(String(20), nullable=False)
    order_public_id = Column(String(120), nullable=False)
    outcome = Column(String(16), nullable=False)
    reveal_count = Column(Integer, nullable=True)
    request_id = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    order = relationship("Order")
    user = relationship("User")

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")


class CashoutRequest(Base):
    __tablename__ = "cashout_requests"
    __table_args__ = (Index("ix_cashout_requests_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    source_platform = Column(String(100), nullable=False)
    custom_source = Column(String(200), nullable=True)
    details_text = Column(Text, nullable=False)
    status = Column(
        postgres_enum(CashoutRequestStatus, "cashoutrequeststatus"),
        default=CashoutRequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="cashout_requests")


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_actor_created", "actor_telegram_id", "created_at"),
        Index("ix_admin_audit_action_created", "action", "created_at"),
        Index("ix_admin_audit_outcome_created", "outcome", "created_at"),
        CheckConstraint(
            "outcome IN ('success', 'rejected', 'failed', 'requested')",
            name="ck_admin_audit_outcome",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    actor_telegram_id = Column(String, nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(180), nullable=True)
    outcome = Column(String(16), nullable=False, default="success")
    request_id = Column(String(64), nullable=True)
    update_id = Column(BigInteger, nullable=True)
    chat_id = Column(String(24), nullable=True)
    reason = Column(String(100), nullable=True)
    old_values = Column(JSON, default=dict, server_default=text("'{}'::json"), nullable=False)
    new_values = Column(JSON, default=dict, server_default=text("'{}'::json"), nullable=False)
    details = Column(
        JSON,
        default=dict,
        server_default=text("'{}'::json"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class TelegramUpdateInbox(Base):
    __tablename__ = "telegram_update_inbox"
    __table_args__ = (
        UniqueConstraint("bot_type", "update_id", name="uq_telegram_update_bot_id"),
        CheckConstraint("bot_type IN ('main', 'admin')", name="ck_telegram_update_bot_type"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'retry', 'done', 'failed')",
            name="ck_telegram_update_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_telegram_update_attempts"),
        CheckConstraint(
            "claim_token IS NULL OR char_length(claim_token) BETWEEN 32 AND 64",
            name="ck_telegram_update_claim_token_length",
        ),
        Index("ix_telegram_update_claim", "status", "next_attempt_at", "id"),
    )

    id = Column(Integer, primary_key=True)
    bot_type = Column(String(10), nullable=False)
    update_id = Column(BigInteger, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    claim_token = Column(String(64), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AdminIdentity(Base):
    __tablename__ = "admin_identities"
    __table_args__ = (
        CheckConstraint("char_length(telegram_id) BETWEEN 1 AND 20", name="ck_admin_identity_telegram_id_length"),
    )

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(20), nullable=False, unique=True)
    display_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_break_glass = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AdminRoleGrant(Base):
    __tablename__ = "admin_role_grants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('superadmin', 'finance', 'catalog', 'support', 'auditor')",
            name="ck_admin_role_grant_role",
        ),
        Index(
            "uq_admin_role_grant_active",
            "admin_identity_id",
            "role",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True)
    admin_identity_id = Column(Integer, ForeignKey("admin_identities.id"), nullable=False)
    role = Column(String(20), nullable=False)
    granted_by_telegram_id = Column(String(20), nullable=False)
    revoked_by_telegram_id = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class AdminActionNonce(Base):
    __tablename__ = "admin_action_nonces"
    __table_args__ = (
        UniqueConstraint("nonce_hash", name="uq_admin_action_nonce_hash"),
        Index("ix_admin_action_nonce_expiry", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    nonce_hash = Column(String(64), nullable=False)
    actor_telegram_id = Column(String(20), nullable=False)
    chat_id = Column(String(24), nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(180), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AdminApprovalRequest(Base):
    __tablename__ = "admin_approval_requests"
    __table_args__ = (
        CheckConstraint("required_approvals >= 2", name="ck_admin_approval_required_count"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'executed', 'expired', 'cancelled')",
            name="ck_admin_approval_status",
        ),
        Index("ix_admin_approval_pending", "status", "expires_at", "id"),
    )

    id = Column(Integer, primary_key=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(180), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    requested_by_telegram_id = Column(String(20), nullable=False)
    required_approvals = Column(Integer, nullable=False, default=2)
    status = Column(String(20), nullable=False, default="pending")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AdminApprovalVote(Base):
    __tablename__ = "admin_approval_votes"
    __table_args__ = (
        UniqueConstraint("approval_request_id", "actor_telegram_id", name="uq_admin_approval_actor"),
    )

    id = Column(Integer, primary_key=True)
    approval_request_id = Column(Integer, ForeignKey("admin_approval_requests.id"), nullable=False)
    actor_telegram_id = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class UsdtRateOverride(Base):
    __tablename__ = "usdt_rate_override"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_usdt_rate_override_singleton"),
        CheckConstraint("version > 0", name="ck_usdt_rate_override_version"),
        CheckConstraint(
            "(is_active AND rate IS NOT NULL AND rate > 0) "
            "OR (NOT is_active AND rate IS NULL)",
            name="ck_usdt_rate_override_state",
        ),
    )

    id = Column(Integer, primary_key=True)
    rate = Column(Numeric(precision=24, scale=8), nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    changed_by_telegram_id = Column(String(20), nullable=True)
    change_source = Column(String(32), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class UsdtRateOverrideVersion(Base):
    __tablename__ = "usdt_rate_override_versions"
    __table_args__ = (
        UniqueConstraint("version", name="uq_usdt_rate_override_version"),
        CheckConstraint("version > 0", name="ck_usdt_rate_override_history_version"),
        CheckConstraint(
            "(is_active AND rate IS NOT NULL AND rate > 0) "
            "OR (NOT is_active AND rate IS NULL)",
            name="ck_usdt_rate_override_history_state",
        ),
        Index("ix_usdt_rate_override_history_created", "created_at", "id"),
    )

    id = Column(BigInteger, primary_key=True)
    version = Column(Integer, nullable=False)
    rate = Column(Numeric(precision=24, scale=8), nullable=True)
    is_active = Column(Boolean, nullable=False)
    changed_by_telegram_id = Column(String(20), nullable=True)
    change_source = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
