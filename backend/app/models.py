import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

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
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    currency = Column(String(10), default="IRR", nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
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
    status = Column(Enum(ItemStatus), default=ItemStatus.AVAILABLE, index=True, nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    variant = relationship("ProductVariant", back_populates="inventory_items")

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("inventory_item_id", name="uq_order_inventory_item_id"),)

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    variant_id = Column(String, ForeignKey("product_variants.id"), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    total_amount = Column(Numeric(precision=18, scale=2), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.ACTIVE, index=True, nullable=False)
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
    status = Column(Enum(CashoutRequestStatus), default=CashoutRequestStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="cashout_requests")