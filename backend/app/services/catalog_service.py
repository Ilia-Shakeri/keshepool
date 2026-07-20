import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import InventoryItem, ItemStatus, Product, ProductVariant, utcnow
from app.services.cache_service import (
    CATALOG_CACHE_KEY,
    invalidate_catalog_cache,
    load_catalog_cached,
    read_json,
)

CATALOG_CATEGORIES = {
    "vpn",
    "music",
    "video",
    "ai",
    "social",
    "gaming",
    "tools",
    "edu",
    "finance",
}


class CatalogMutationError(ValueError):
    pass


class VariantOwnershipError(CatalogMutationError):
    def __init__(self, variant_id: str, owner_product_id: str):
        super().__init__(
            f"Variant '{variant_id}' already belongs to product '{owner_product_id}'."
        )
        self.variant_id = variant_id
        self.owner_product_id = owner_product_id


@dataclass(frozen=True)
class VariantMutation:
    id: str
    duration: str
    raw_price: Decimal
    price_label: str
    is_active: bool = True
    credentials: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductMutation:
    id: str
    title: str
    brand: str
    subtitle: str
    icon: str
    asset_url: str | None
    gradient: str
    category: str
    features: tuple[str, ...] | None
    is_active: bool
    variants: tuple[VariantMutation, ...]


@dataclass
class CatalogMutationResult:
    product_id: str
    active: bool
    active_variant_count: int
    inserted_stock_count: int
    duplicate_stock_count: int
    catalog_visibility_reason: str
    cache_invalidated: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StockMutationResult:
    product_id: str
    variant_id: str
    inserted_stock_count: int
    duplicate_stock_count: int
    cache_invalidated: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_product_features(raw_features: str | None) -> list[str] | None:
    if not raw_features:
        return None
    try:
        parsed = json.loads(raw_features)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, list):
        return None
    features = [str(feature).strip() for feature in parsed if str(feature).strip()]
    return features or None


def catalog_visibility_reason(
    *,
    active: bool,
    title: str,
    brand: str,
    category: str,
    active_variant_count: int,
) -> str:
    if not active:
        return "inactive_product"
    if not title.strip() or not brand.strip():
        return "invalid_product_data"
    if category not in CATALOG_CATEGORIES:
        return "invalid_category"
    if active_variant_count < 1:
        return "no_active_variant"
    return "visible"


def _clean_required(value: Any, field: str) -> str:
    clean_value = str(value or "").strip()
    if not clean_value:
        raise CatalogMutationError(f"{field} is required.")
    return clean_value


def _decimal_price(value: Any) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CatalogMutationError("Variant raw_price must be a valid number.") from exc
    if price <= 0:
        raise CatalogMutationError("Variant raw_price must be positive.")
    return price


def _mapping_boolean(
    payload: Mapping[str, Any],
    snake_name: str,
    camel_name: str,
    *,
    default: bool,
) -> bool:
    if snake_name in payload:
        value = payload[snake_name]
    elif camel_name in payload:
        value = payload[camel_name]
    else:
        return default
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise CatalogMutationError(f"{snake_name} must be a boolean.")


def product_mutation_from_mapping(payload: Mapping[str, Any]) -> ProductMutation:
    category = str(payload.get("category") or "tools").strip()
    if category not in CATALOG_CATEGORIES:
        raise CatalogMutationError(f"Unsupported product category '{category}'.")

    raw_features = payload.get("features")
    if raw_features is None:
        features = None
    elif isinstance(raw_features, Sequence) and not isinstance(raw_features, (str, bytes)):
        features = tuple(str(item).strip() for item in raw_features if str(item).strip()) or None
    else:
        raise CatalogMutationError("Product features must be a list.")

    raw_variants = payload.get("variants")
    if not isinstance(raw_variants, Sequence) or isinstance(raw_variants, (str, bytes)):
        raise CatalogMutationError("Product variants must be a list.")

    variants: list[VariantMutation] = []
    seen_variant_ids: set[str] = set()
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, Mapping):
            raise CatalogMutationError("Each product variant must be an object.")
        variant_id = _clean_required(raw_variant.get("id"), "Variant id")
        if variant_id in seen_variant_ids:
            raise CatalogMutationError(f"Variant '{variant_id}' appears more than once.")
        seen_variant_ids.add(variant_id)

        price = _decimal_price(raw_variant.get("raw_price", raw_variant.get("rawPrice")))
        raw_credentials = raw_variant.get("credentials") or ()
        if not isinstance(raw_credentials, Sequence) or isinstance(raw_credentials, (str, bytes)):
            raise CatalogMutationError("Variant credentials must be a list.")
        credentials = tuple(str(item).strip() for item in raw_credentials if str(item).strip())
        variants.append(
            VariantMutation(
                id=variant_id,
                duration=_clean_required(raw_variant.get("duration"), "Variant duration"),
                raw_price=price,
                price_label=str(
                    raw_variant.get("price_label")
                    or raw_variant.get("priceLabel")
                    or f"{int(price):,}"
                ).strip(),
                is_active=_mapping_boolean(
                    raw_variant,
                    "is_active",
                    "isActive",
                    default=True,
                ),
                credentials=credentials,
            )
        )

    return ProductMutation(
        id=_clean_required(payload.get("id"), "Product id"),
        title=_clean_required(payload.get("title"), "Product title"),
        brand=_clean_required(payload.get("brand"), "Product brand"),
        subtitle=str(payload.get("subtitle") or "").strip(),
        icon=str(payload.get("icon") or "Box").strip(),
        asset_url=payload.get("asset_url", payload.get("assetUrl")),
        gradient=str(payload.get("gradient") or "from-gray-700 to-black").strip(),
        category=category,
        features=features,
        is_active=_mapping_boolean(payload, "is_active", "isActive", default=True),
        variants=tuple(variants),
    )


async def _insert_inventory_rows(
    db: AsyncSession,
    product_id: str,
    variant_credentials: Iterable[tuple[str, str]],
) -> tuple[int, int]:
    submitted_rows: list[dict[str, Any]] = []
    for variant_id, credential in variant_credentials:
        clean_credential = credential.strip()
        if clean_credential:
            submitted_rows.append(
                {
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "credentials": clean_credential,
                    "status": ItemStatus.AVAILABLE,
                }
            )

    if not submitted_rows:
        return 0, 0

    inserted_count = 0
    # Keep each statement below PostgreSQL's bind-parameter limit for large imports.
    for offset in range(0, len(submitted_rows), 5_000):
        statement = (
            pg_insert(InventoryItem)
            .values(submitted_rows[offset : offset + 5_000])
            .on_conflict_do_nothing(constraint="uq_inventory_unique_credentials")
            .returning(InventoryItem.id)
        )
        result = await db.execute(statement)
        inserted_count += len(result.scalars().all())
    return inserted_count, len(submitted_rows) - inserted_count


async def commit_catalog_change(db: AsyncSession) -> bool:
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await invalidate_catalog_cache()


async def upsert_product(
    db: AsyncSession,
    payload: ProductMutation | Mapping[str, Any],
    *,
    replace_variants: bool,
    commit: bool = True,
) -> CatalogMutationResult:
    mutation = (
        payload if isinstance(payload, ProductMutation) else product_mutation_from_mapping(payload)
    )
    incoming_variant_ids = {variant.id for variant in mutation.variants}

    if incoming_variant_ids:
        collision_result = await db.execute(
            select(ProductVariant)
            .where(ProductVariant.id.in_(incoming_variant_ids))
            .with_for_update()
        )
        for existing_variant in collision_result.scalars().all():
            if existing_variant.product_id != mutation.id:
                raise VariantOwnershipError(existing_variant.id, existing_variant.product_id)

    product_result = await db.execute(
        select(Product).where(Product.id == mutation.id).with_for_update()
    )
    product = product_result.scalars().first()
    if product is None:
        product = Product(id=mutation.id)
        db.add(product)

    product.title = mutation.title
    product.brand = mutation.brand
    product.subtitle = mutation.subtitle
    product.icon = mutation.icon
    product.asset_url = mutation.asset_url
    product.gradient = mutation.gradient
    product.category = mutation.category
    product.features = (
        json.dumps(mutation.features, ensure_ascii=False) if mutation.features else None
    )
    product.is_active = mutation.is_active

    existing_result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == mutation.id)
        .with_for_update()
    )
    existing_variants = {variant.id: variant for variant in existing_result.scalars().all()}

    stock_rows: list[tuple[str, str]] = []
    for variant_mutation in mutation.variants:
        variant = existing_variants.get(variant_mutation.id)
        if variant is None:
            variant = ProductVariant(id=variant_mutation.id, product_id=mutation.id)
            db.add(variant)
            existing_variants[variant.id] = variant
        variant.duration = variant_mutation.duration
        variant.raw_price = variant_mutation.raw_price
        variant.price_label = variant_mutation.price_label
        variant.is_active = variant_mutation.is_active
        stock_rows.extend(
            (variant_mutation.id, credential)
            for credential in variant_mutation.credentials
        )

    if replace_variants:
        for variant_id, variant in existing_variants.items():
            if variant_id not in incoming_variant_ids:
                variant.is_active = False

    await db.flush()
    inserted_count, duplicate_count = await _insert_inventory_rows(
        db, mutation.id, stock_rows
    )
    active_variant_count = int(
        await db.scalar(
            select(func.count(ProductVariant.id)).where(
                ProductVariant.product_id == mutation.id,
                ProductVariant.is_active.is_(True),
            )
        )
        or 0
    )
    result = CatalogMutationResult(
        product_id=mutation.id,
        active=mutation.is_active,
        active_variant_count=active_variant_count,
        inserted_stock_count=inserted_count,
        duplicate_stock_count=duplicate_count,
        catalog_visibility_reason=catalog_visibility_reason(
            active=mutation.is_active,
            title=mutation.title,
            brand=mutation.brand,
            category=mutation.category,
            active_variant_count=active_variant_count,
        ),
    )
    if commit:
        result.cache_invalidated = await commit_catalog_change(db)
    return result


async def bulk_insert_stock(
    db: AsyncSession,
    *,
    product_id: str,
    variant_id: str,
    credentials: Sequence[str],
    commit: bool = True,
) -> StockMutationResult:
    variant_result = await db.execute(
        select(ProductVariant)
        .where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
        .with_for_update()
    )
    if variant_result.scalars().first() is None:
        raise CatalogMutationError("Product variant not found.")

    inserted_count, duplicate_count = await _insert_inventory_rows(
        db,
        product_id,
        ((variant_id, credential) for credential in credentials),
    )
    result = StockMutationResult(
        product_id=product_id,
        variant_id=variant_id,
        inserted_stock_count=inserted_count,
        duplicate_stock_count=duplicate_count,
    )
    if commit:
        result.cache_invalidated = await commit_catalog_change(db)
    return result


async def set_product_active(
    db: AsyncSession,
    product_id: str,
    active: bool,
    *,
    deactivate_variants: bool = False,
    commit: bool = True,
) -> Product:
    product_result = await db.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    product = product_result.scalars().first()
    if product is None:
        raise CatalogMutationError("Product not found.")
    product.is_active = active
    if deactivate_variants:
        variants_result = await db.execute(
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .with_for_update()
        )
        for variant in variants_result.scalars().all():
            variant.is_active = False
    if commit:
        await commit_catalog_change(db)
    return product


async def patch_product_fields(
    db: AsyncSession,
    product_id: str,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> Product:
    allowed_fields = {
        "title",
        "brand",
        "subtitle",
        "icon",
        "asset_url",
        "gradient",
        "category",
        "features",
    }
    unknown_fields = set(values) - allowed_fields
    if unknown_fields:
        raise CatalogMutationError(
            f"Unsupported product fields: {', '.join(sorted(unknown_fields))}."
        )
    product_result = await db.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    product = product_result.scalars().first()
    if product is None:
        raise CatalogMutationError("Product not found.")
    for field, value in values.items():
        setattr(product, field, value)
    if commit:
        await commit_catalog_change(db)
    return product


async def patch_product(
    db: AsyncSession,
    product_id: str,
    *,
    values: Mapping[str, Any] | None = None,
    active: bool | None = None,
    raw_price: Decimal | None = None,
    variant_id: str | None = None,
) -> CatalogMutationResult:
    values = values or {}
    allowed_fields = {
        "title",
        "brand",
        "subtitle",
        "icon",
        "asset_url",
        "gradient",
        "category",
        "features",
    }
    unknown_fields = set(values) - allowed_fields
    if unknown_fields:
        raise CatalogMutationError(
            f"Unsupported product fields: {', '.join(sorted(unknown_fields))}."
        )

    product_result = await db.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    product = product_result.scalars().first()
    if product is None:
        raise CatalogMutationError("Product not found.")

    for field, value in values.items():
        if field == "features" and value is not None and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        setattr(product, field, value)
    if active is not None:
        product.is_active = active

    variants_result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .with_for_update()
    )
    variants = variants_result.scalars().all()
    if raw_price is not None:
        if raw_price <= 0:
            raise CatalogMutationError("Variant price must be positive.")
        matched_variants = [
            variant
            for variant in variants
            if (variant.id == variant_id if variant_id else variant.is_active)
        ]
        if variant_id and not matched_variants:
            raise CatalogMutationError("Product variant not found.")
        for variant in matched_variants:
            variant.raw_price = raw_price
            variant.price_label = f"{int(raw_price):,}"

    await db.flush()
    active_variant_count = sum(1 for variant in variants if variant.is_active)
    result = CatalogMutationResult(
        product_id=product.id,
        active=product.is_active,
        active_variant_count=active_variant_count,
        inserted_stock_count=0,
        duplicate_stock_count=0,
        catalog_visibility_reason=catalog_visibility_reason(
            active=product.is_active,
            title=product.title,
            brand=product.brand,
            category=product.category,
            active_variant_count=active_variant_count,
        ),
    )
    result.cache_invalidated = await commit_catalog_change(db)
    return result


async def set_active_variant_prices(
    db: AsyncSession,
    product_id: str,
    raw_price: Decimal,
    *,
    commit: bool = True,
) -> int:
    if raw_price <= 0:
        raise CatalogMutationError("Variant price must be positive.")
    variants_result = await db.execute(
        select(ProductVariant)
        .where(
            ProductVariant.product_id == product_id,
            ProductVariant.is_active.is_(True),
        )
        .with_for_update()
    )
    variants = variants_result.scalars().all()
    for variant in variants:
        variant.raw_price = raw_price
        variant.price_label = f"{int(raw_price):,}"
    if commit:
        await commit_catalog_change(db)
    return len(variants)


async def build_public_catalog(db: AsyncSession) -> list[dict[str, Any]]:
    now = utcnow()
    stock_result = await db.execute(
        select(InventoryItem.variant_id, func.count(InventoryItem.id))
        .where(
            InventoryItem.status == ItemStatus.AVAILABLE,
            or_(InventoryItem.expires_at.is_(None), InventoryItem.expires_at > now),
        )
        .group_by(InventoryItem.variant_id)
    )
    stock_by_variant = {
        variant_id: count for variant_id, count in stock_result.all()
    }
    product_result = await db.execute(
        select(Product)
        .options(selectinload(Product.variants))
        .where(Product.is_active.is_(True))
        .order_by(Product.created_at.desc())
    )

    output: list[dict[str, Any]] = []
    for product in product_result.scalars().all():
        active_variants = [variant for variant in product.variants if variant.is_active]
        if catalog_visibility_reason(
            active=product.is_active,
            title=product.title,
            brand=product.brand,
            category=product.category,
            active_variant_count=len(active_variants),
        ) != "visible":
            continue
        output.append(
            {
                "id": product.id,
                "title": product.title,
                "brand": product.brand,
                "subtitle": product.subtitle or "",
                "icon": product.icon or "Box",
                "assetUrl": product.asset_url,
                "gradient": product.gradient or "from-gray-700 to-black",
                "category": product.category or "tools",
                "features": parse_product_features(product.features),
                "variants": [
                    {
                        "id": variant.id,
                        "duration": variant.duration,
                        "priceLabel": variant.price_label,
                        "rawPrice": float(variant.raw_price),
                        "stockCount": int(stock_by_variant.get(variant.id, 0)),
                    }
                    for variant in active_variants
                ],
            }
        )
    return output


async def get_public_catalog(db: AsyncSession) -> list[dict[str, Any]]:
    return await load_catalog_cached(lambda: build_public_catalog(db))


async def catalog_diagnostics(
    db: AsyncSession,
    product_id: str,
) -> dict[str, Any]:
    product_result = await db.execute(
        select(Product).options(selectinload(Product.variants)).where(Product.id == product_id)
    )
    product = product_result.scalars().first()
    if product is None:
        return {
            "product_id": product_id,
            "visibility_reason": "not_found",
            "cache_status": "unknown",
        }

    active_variant_count = sum(1 for variant in product.variants if variant.is_active)
    available_stock = int(
        await db.scalar(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.product_id == product_id,
                InventoryItem.status == ItemStatus.AVAILABLE,
                or_(
                    InventoryItem.expires_at.is_(None),
                    InventoryItem.expires_at > utcnow(),
                ),
            )
        )
        or 0
    )
    cache_read = await read_json(CATALOG_CACHE_KEY)
    if not cache_read.available:
        cache_status = "unavailable"
    elif not cache_read.hit:
        cache_status = "miss"
    else:
        cached_product_ids = {
            item.get("id") for item in cache_read.value if isinstance(item, dict)
        } if isinstance(cache_read.value, list) else set()
        expected_visible = product.is_active and active_variant_count > 0
        cache_matches = (product_id in cached_product_ids) == expected_visible
        cache_status = "healthy" if cache_matches else "stale"

    return {
        "product_id": product.id,
        "active": product.is_active,
        "active_variant_count": active_variant_count,
        "available_stock_count": available_stock,
        "visibility_reason": catalog_visibility_reason(
            active=product.is_active,
            title=product.title,
            brand=product.brand,
            category=product.category,
            active_variant_count=active_variant_count,
        ),
        "cache_status": cache_status,
    }
