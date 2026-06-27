"""
Detects pre-Alembic databases bootstrapped via SQLAlchemy create_all() and
stamps the baseline migration (001) so that alembic upgrade head only applies
the additive schema changes, not full table recreation.

Exit codes:
  0  - no action needed (fresh install or alembic already initialised)
  1  - fatal error
"""
import asyncio
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, "/app")

from app.core.config import settings


async def detect_and_stamp() -> int:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            alembic_exists: bool = await conn.scalar(text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'public' AND table_name = 'alembic_version'"
                ")"
            ))
            users_exists: bool = await conn.scalar(text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'public' AND table_name = 'users'"
                ")"
            ))
    finally:
        await engine.dispose()

    if alembic_exists:
        print("[migration-check] alembic_version table found — no stamp needed.")
        return 0

    if not users_exists:
        print("[migration-check] Fresh database — alembic will build schema from scratch.")
        return 0

    # Legacy database: schema exists but has never been tracked by Alembic.
    # Mark migration 001 as already applied so it is not re-executed.
    print("[migration-check] Legacy (pre-Alembic) database detected — stamping revision 001...")
    result = subprocess.run(
        ["alembic", "stamp", "001"],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        print("[migration-check] ERROR: alembic stamp failed.", file=sys.stderr)
        return 1

    print("[migration-check] Baseline stamped. Pending migrations will be applied next.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(detect_and_stamp()))
