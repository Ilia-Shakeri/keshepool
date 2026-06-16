from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()

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
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship("Wallet", back_populates="user", uselist=False)

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    balance = Column(Numeric(precision=18, scale=2), default=0.00)
    
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"))
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    reference_id = Column(String, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship("Wallet", back_populates="transactions")

class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    subtitle = Column(String)
    icon = Column(String, default="Box") 
    gradient = Column(String, default="from-gray-700 to-black")
    category = Column(String, default="tools")
    
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")

class ProductVariant(Base):
    __tablename__ = "product_variants"
    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"))
    duration = Column(String, nullable=False)
    price_label = Column(String, nullable=False)
    raw_price = Column(Numeric(precision=18, scale=2), nullable=False)
    
    product = relationship("Product", back_populates="variants")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True)
    variant_id = Column(String, ForeignKey("product_variants.id"), nullable=True) 
    credentials = Column(String) 
    status = Column(Enum(ItemStatus), default=ItemStatus.AVAILABLE)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)