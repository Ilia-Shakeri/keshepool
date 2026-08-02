import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
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
        UniqueConstraint("product_id", "variant_id", "credentials", name="uq_inventory_unique_credentials"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True, nullable=False)
    variant_id = Column(String, ForeignKey("product_variants.id"), index=True, nullable=False)
    credentials = Column(Text, nullable=False)
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
        Index(
            "uq_orders_user_idempotency_key",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    variant_id = Column(String, ForeignKey("product_variants.id"), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    total_amount = Column(Numeric(precision=18, scale=2), nullable=False)
    idempotency_key = Column(String(64), nullable=True)
    status = Column(
        postgres_enum(OrderStatus, "orderstatus"),
        default=OrderStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="orders")
    product = relationship("Product")
    variant = relationship("ProductVariant")
    inventory_item = relationship("InventoryItem")

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
    )

    id = Column(Integer, primary_key=True, index=True)
    actor_telegram_id = Column(String, nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(180), nullable=True)
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
