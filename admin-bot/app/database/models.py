from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()

# Mirroring existing DB enumerations
class ItemStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    ASSIGNED = "assigned"
    EXPIRED = "expired"
    DISABLED = "disabled"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    balance = Column(Numeric(precision=18, scale=2), default=0.00)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, index=True)
    plan_type = Column(String)
    credentials = Column(String)
    status = Column(Enum(ItemStatus), default=ItemStatus.AVAILABLE)

# Synced models from the backend to allow admin management
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