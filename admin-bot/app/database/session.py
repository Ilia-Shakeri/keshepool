from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Utilize the validated database connection string
engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    """Yields a database session and ensures it is closed after execution."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()