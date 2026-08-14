from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_REQUIRED_TABLES = frozenset(
    {
        "users",
        "wallets",
        "transactions",
        "products",
        "product_variants",
        "inventory_items",
        "orders",
        "alembic_version",
    }
)


@dataclass(frozen=True)
class SchemaCompatibility:
    ready: bool
    current_revisions: tuple[str, ...]
    expected_revisions: tuple[str, ...]
    missing_tables: tuple[str, ...]


@lru_cache(maxsize=1)
def expected_schema_heads() -> tuple[str, ...]:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    heads = tuple(sorted(ScriptDirectory.from_config(config).get_heads()))
    if len(heads) != 1:
        raise RuntimeError("The release must contain exactly one migration head.")
    return heads


async def check_schema_compatibility(session: AsyncSession) -> SchemaCompatibility:
    revision_result = await session.execute(text("SELECT version_num FROM alembic_version"))
    current = tuple(sorted(str(value) for value in revision_result.scalars().all()))
    expected = expected_schema_heads()

    table_result = await session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name IN ("
            "'users', 'wallets', 'transactions', 'products', 'product_variants', "
            "'inventory_items', 'orders', 'alembic_version')"
        )
    )
    present = {str(value) for value in table_result.scalars().all()}
    missing = tuple(sorted(_REQUIRED_TABLES - present))
    return SchemaCompatibility(
        ready=current == expected and not missing,
        current_revisions=current,
        expected_revisions=expected,
        missing_tables=missing,
    )


def schema_health_payload(result: SchemaCompatibility) -> dict[str, object]:
    return {
        "ok": result.ready,
        "currentRevision": list(result.current_revisions),
        "expectedRevision": list(result.expected_revisions),
        "missingTables": list(result.missing_tables),
    }
