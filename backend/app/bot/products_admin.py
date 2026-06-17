import csv
import io
import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Product, ProductVariant, InventoryItem, ItemStatus

logger = logging.getLogger(__name__)
products_router = Router()

class ProductAdminStates(StatesGroup):
    awaiting_bulk_import_file = State()

ALLOWED_CATEGORIES = {"vpn", "music", "video", "ai", "social", "gaming", "tools", "edu", "finance"}
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{2,120}$")

def _validate_id(value: str, field: str) -> str:
    clean = value.strip()
    if not SAFE_ID_RE.match(clean):
        raise ValueError(f"{field} must contain only valid characters.")
    return clean

def parse_product_import(content: str) -> Tuple[List[Dict], List[str]]:
    rows: List[Dict] = []
    errors: List[str] = []
    reader = csv.reader(io.StringIO(content), delimiter="|")

    for index, row in enumerate(reader, start=1):
        if not row or not "".join(row).strip() or row[0].strip().startswith("#"):
            continue

        if len(row) < 8:
            errors.append(f"Line {index}: expected at least 8 pipe-separated columns.")
            continue

        try:
            product_id = _validate_id(row[0], "product_id")
            variant_id = _validate_id(row[5], "variant_id")
            category = row[4].strip() or "tools"
            
            if category not in ALLOWED_CATEGORIES:
                raise ValueError("Invalid category.")

            raw_price = Decimal(row[7].strip())
            if raw_price <= 0:
                raise ValueError("raw_price must be positive.")

            credentials = []
            if len(row) >= 9 and row[8].strip():
                credentials = [item.strip() for item in row[8].split(";") if item.strip()]

            rows.append({
                "product_id": product_id,
                "title": row[1].strip(),
                "brand": row[2].strip(),
                "subtitle": row[3].strip(),
                "category": category,
                "variant_id": variant_id,
                "duration": row[6].strip(),
                "raw_price": float(raw_price),
                "credentials": credentials,
            })
        except (InvalidOperation, ValueError) as exc:
            errors.append(f"Line {index}: {exc}")

    return rows, errors

@products_router.message(ProductAdminStates.awaiting_bulk_import_file, F.document)
async def process_bulk_import_file(message: Message, state: FSMContext):
    document = message.document

    if not document.file_name.lower().endswith(".txt"):
        await message.answer("Please upload a .txt file.")
        return

    buffer = io.BytesIO()
    await message.bot.download(document, destination=buffer)
    content = buffer.getvalue().decode("utf-8-sig", errors="replace")
    rows, errors = parse_product_import(content)

    if errors:
        await message.answer("Import file has validation errors:\n" + "\n".join(errors[:10]))
        return

    inserted_credentials = 0
    chunk_size = 50
    chunk_errors = []

    # Process batch inserts with sequential fallback for exact error tracking
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        async with AsyncSessionLocal() as session:
            try:
                for row in chunk:
                    product_id = row["product_id"]
                    variant_id = row["variant_id"]
                    
                    product = await session.get(Product, product_id)
                    if not product:
                        product = Product(
                            id=product_id,
                            title=row["title"],
                            brand=row["brand"],
                            subtitle=row["subtitle"],
                            category=row["category"],
                            is_active=True
                        )
                        session.add(product)
                    
                    variant = await session.get(ProductVariant, variant_id)
                    if not variant:
                        variant = ProductVariant(
                            id=variant_id,
                            product_id=product_id,
                            duration=row["duration"],
                            raw_price=row["raw_price"],
                            price_label=f"{int(row['raw_price']):,}",
                            is_active=True
                        )
                        session.add(variant)

                    if row["credentials"]:
                        for cred in row["credentials"]:
                            exists_result = await session.execute(
                                select(InventoryItem).where(
                                    InventoryItem.product_id == product_id,
                                    InventoryItem.variant_id == variant_id,
                                    InventoryItem.credentials == cred
                                )
                            )
                            
                            if not exists_result.scalars().first():
                                session.add(InventoryItem(
                                    product_id=product_id,
                                    variant_id=variant_id,
                                    credentials=cred,
                                    status=ItemStatus.AVAILABLE
                                ))
                                inserted_credentials += 1
                                
                await session.commit()
                
            except Exception as bulk_exc:
                # Isolate the failure by rolling back the chunk and falling back to sequential processing
                await session.rollback()
                logger.warning("Bulk chunk failed, falling back to sequential tracking. Exception: %s", bulk_exc)
                
                for j, row in enumerate(chunk):
                    async with AsyncSessionLocal() as single_session:
                        try:
                            product_id = row["product_id"]
                            variant_id = row["variant_id"]
                            
                            product = await single_session.get(Product, product_id)
                            if not product:
                                product = Product(
                                    id=product_id,
                                    title=row["title"],
                                    brand=row["brand"],
                                    subtitle=row["subtitle"],
                                    category=row["category"],
                                    is_active=True
                                )
                                single_session.add(product)
                            
                            variant = await single_session.get(ProductVariant, variant_id)
                            if not variant:
                                variant = ProductVariant(
                                    id=variant_id,
                                    product_id=product_id,
                                    duration=row["duration"],
                                    raw_price=row["raw_price"],
                                    price_label=f"{int(row['raw_price']):,}",
                                    is_active=True
                                )
                                single_session.add(variant)
                                
                            if row["credentials"]:
                                for cred in row["credentials"]:
                                    exists_result = await single_session.execute(
                                        select(InventoryItem).where(
                                            InventoryItem.product_id == product_id,
                                            InventoryItem.variant_id == variant_id,
                                            InventoryItem.credentials == cred
                                        )
                                    )
                                    
                                    if not exists_result.scalars().first():
                                        single_session.add(InventoryItem(
                                            product_id=product_id,
                                            variant_id=variant_id,
                                            credentials=cred,
                                            status=ItemStatus.AVAILABLE
                                        ))
                                        inserted_credentials += 1
                                        
                            await single_session.commit()
                        except Exception as single_exc:
                            await single_session.rollback()
                            exact_line = i + j + 1
                            error_msg = f"Line {exact_line} (Product: {row['product_id']}) failed: {single_exc}"
                            chunk_errors.append(error_msg)
                            logger.error(error_msg)

    await state.clear()
    
    if chunk_errors:
        error_report = "Import encountered database constraint errors on specific rows:\n" + "\n".join(chunk_errors[:10])
        if len(chunk_errors) > 10:
            error_report += f"\n...and {len(chunk_errors) - 10} more errors."
        await message.answer(error_report)
    else:
        await message.answer(f"Bulk import success.\nProducts processed: {len(rows)}\nCredentials added: {inserted_credentials}")