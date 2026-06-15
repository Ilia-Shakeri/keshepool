from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()

# Define standardized statuses for the inventory lifecycle
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

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="user") # 'admin' or 'user'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    balance = Column(Numeric(precision=18, scale=2), default=0.00)
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"))
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    reference_id = Column(String, nullable=True) # E.g., Tetra98 transaction ID
    created_at = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship("Wallet", back_populates="transactions")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, index=True) # Links to frontend product IDs
    plan_type = Column(String) # e.g., '1m_basic', 'plan1_v2ray'
    credentials = Column(String) # Encrypted string or config URI
    status = Column(Enum(ItemStatus), default=ItemStatus.AVAILABLE)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)