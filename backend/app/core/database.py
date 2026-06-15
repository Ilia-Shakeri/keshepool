# ==================================================
# FILE: backend/app/core/database.py
# ==================================================

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Construct the async database URL from the environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/dbname")

# Create the async SQLAlchemy engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create the session factory for async sessions
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """
    Dependency function to yield database sessions for FastAPI routes.
    Ensures the session is cleanly closed after the request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()