from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CashoutRequest,
    InventoryItem,
    ItemStatus,
    Order,
    OrderStatus,
    Product,
    ProductVariant,
    Transaction,
    TransactionStatus,
    User,
    Wallet,
    utcnow,
)

FONT_NAME = "KeshepoolReportFont"
FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
LOW_STOCK_THRESHOLD = 5
TOP_PRODUCT_LIMIT = 10
LOW_STOCK_DETAIL_LIMIT = 20


def _register_font() -> None:
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    font_path = next((path for path in FONT_CANDIDATES if path.exists()), None)
    if font_path is None:
        raise RuntimeError("A Unicode report font is required.")
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))


def _display(value: object, lang: str) -> str:
    text = str(value if value is not None else "—")
    if lang == "fa":
        text = get_display(arabic_reshaper.reshape(text))
    return escape(text)


def _number(value: object) -> str:
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


async def collect_system_report(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
) -> dict[str, object]:
    user_counts = {
        "total": int(
            await session.scalar(
                select(func.count(User.id)).where(User.created_at < end)
            )
            or 0
        ),
        "new": int(
            await session.scalar(
                select(func.count(User.id)).where(
                    User.created_at >= start,
                    User.created_at < end,
                )
            )
            or 0
        ),
        "active": int(
            await session.scalar(
                select(func.count(User.id)).where(
                    User.last_seen_at >= start,
                    User.last_seen_at < end,
                )
            )
            or 0
        ),
        "banned": int(
            await session.scalar(
                select(func.count(User.id)).where(
                    User.created_at < end,
                    User.is_banned.is_(True),
                )
            )
            or 0
        ),
    }
    wallet_total = await session.scalar(select(func.coalesce(func.sum(Wallet.balance), 0)))

    order_rows = (
        await session.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.created_at >= start, Order.created_at < end)
            .group_by(Order.status)
        )
    ).all()
    orders_by_status = {
        status.value if hasattr(status, "value") else str(status): int(count)
        for status, count in order_rows
    }
    delivered_revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.created_at >= start,
            Order.created_at < end,
            Order.status == OrderStatus.ACTIVE,
        )
    )
    top_products = (
        await session.execute(
            select(
                Product.title,
                func.count(Order.id).label("sales"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .join(Order, Order.product_id == Product.id)
            .where(
                Order.created_at >= start,
                Order.created_at < end,
                Order.status == OrderStatus.ACTIVE,
            )
            .group_by(Product.id, Product.title)
            .order_by(func.count(Order.id).desc(), Product.title.asc())
            .limit(TOP_PRODUCT_LIMIT)
        )
    ).all()

    transaction_rows = (
        await session.execute(
            select(Transaction.status, func.count(Transaction.id))
            .where(Transaction.created_at >= start, Transaction.created_at < end)
            .group_by(Transaction.status)
        )
    ).all()
    transactions_by_status = {
        status.value if hasattr(status, "value") else str(status): int(count)
        for status, count in transaction_rows
    }
    transaction_totals = (
        await session.execute(
            select(Transaction.currency, func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.created_at >= start,
                Transaction.created_at < end,
                Transaction.status == TransactionStatus.SUCCESS,
            )
            .group_by(Transaction.currency)
            .order_by(Transaction.currency.asc())
        )
    ).all()

    cashout_rows = (
        await session.execute(
            select(CashoutRequest.status, func.count(CashoutRequest.id))
            .where(CashoutRequest.created_at >= start, CashoutRequest.created_at < end)
            .group_by(CashoutRequest.status)
        )
    ).all()
    cashouts_by_status = {
        status.value if hasattr(status, "value") else str(status): int(count)
        for status, count in cashout_rows
    }

    active_products = int(
        await session.scalar(
            select(func.count(Product.id)).where(Product.is_active.is_(True))
        )
        or 0
    )
    now = utcnow()
    plan_rows = (
        await session.execute(
            select(
                Product.title,
                ProductVariant.duration,
                func.count(
                    case(
                        (
                            and_(
                                InventoryItem.status == ItemStatus.AVAILABLE,
                                (InventoryItem.expires_at.is_(None))
                                | (InventoryItem.expires_at > now),
                            ),
                            InventoryItem.id,
                        )
                    )
                ).label("stock"),
            )
            .select_from(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id)
            .outerjoin(InventoryItem, InventoryItem.variant_id == ProductVariant.id)
            .where(
                Product.is_active.is_(True),
                ProductVariant.is_active.is_(True),
            )
            .group_by(ProductVariant.id, Product.title, ProductVariant.duration)
            .order_by(Product.title.asc(), ProductVariant.duration.asc())
        )
    ).all()
    low_stock_rows = [
        {"product": title, "plan": duration, "stock": int(stock)}
        for title, duration, stock in plan_rows
        if int(stock) <= LOW_STOCK_THRESHOLD
    ]

    return {
        "users": user_counts,
        "wallet_total": wallet_total or 0,
        "orders_by_status": orders_by_status,
        "delivered_revenue": delivered_revenue or 0,
        "top_products": [
            {"product": title, "sales": int(sales), "revenue": revenue}
            for title, sales, revenue in top_products
        ],
        "transactions_by_status": transactions_by_status,
        "transaction_totals": [
            {"currency": currency, "total": total}
            for currency, total in transaction_totals
        ],
        "cashouts_by_status": cashouts_by_status,
        "catalog": {
            "active_products": active_products,
            "active_plans": len(plan_rows),
            "sellable_stock": sum(int(stock) for _, _, stock in plan_rows),
            "low_stock_plans": len(low_stock_rows),
            "zero_stock_plans": sum(1 for row in low_stock_rows if row["stock"] == 0),
        },
        "low_stock_detail": low_stock_rows[:LOW_STOCK_DETAIL_LIMIT],
    }


def make_system_report_pdf(
    report: dict[str, object],
    *,
    start_label: str,
    end_label: str,
    lang: str,
) -> bytes:
    _register_font()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title="Keshepool full report",
    )
    alignment = TA_RIGHT if lang == "fa" else TA_LEFT
    body = ParagraphStyle(
        "SystemReportBody",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=12,
        alignment=alignment,
    )
    title_style = ParagraphStyle(
        "SystemReportTitle",
        parent=body,
        fontSize=16,
        leading=22,
        textColor=colors.HexColor("#B4232D"),
    )
    section_style = ParagraphStyle(
        "SystemReportSection",
        parent=body,
        fontSize=11,
        leading=16,
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
    )
    labels = {
        "title": "گزارش کلی کش‌پول" if lang == "fa" else "Keshepool Full Report",
        "period": "بازه گزارش" if lang == "fa" else "Report period",
        "users": "کاربران" if lang == "fa" else "Users",
        "wallet": "مجموع موجودی کیف پول‌ها" if lang == "fa" else "Wallet balance total",
        "orders": "سفارش‌ها و فروش" if lang == "fa" else "Orders and sales",
        "revenue": "درآمد فروش تحویل‌شده" if lang == "fa" else "Delivered-sales revenue",
        "top": "محصولات پرفروش" if lang == "fa" else "Top products",
        "transactions": "تراکنش‌ها" if lang == "fa" else "Transactions",
        "cashouts": "درخواست‌های نقد کردن درآمد ارزی" if lang == "fa" else "Foreign-income cashouts",
        "catalog": "کاتالوگ و موجودی" if lang == "fa" else "Catalog and inventory",
        "low": "پلن‌های کم‌موجود یا ناموجود" if lang == "fa" else "Low and zero-stock plans",
    }
    story = [
        Paragraph(_display(labels["title"], lang), title_style),
        Paragraph(
            _display(f"{labels['period']}: {start_label} — {end_label}", lang),
            body,
        ),
        Spacer(1, 2 * mm),
    ]

    def add_section(title: str, rows: list[tuple[object, object]]) -> None:
        table_data = [
            [
                Paragraph(_display(label, lang), body),
                Paragraph(_display(_number(value), lang), body),
            ]
            for label, value in rows
        ]
        table = Table(table_data, colWidths=[118 * mm, 54 * mm], hAlign="RIGHT")
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C7C7C7")),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(
            KeepTogether(
                [
                    Paragraph(_display(title, lang), section_style),
                    table,
                ]
            )
        )

    users = report.get("users", {})
    user_labels = (
        {"total": "کل", "new": "جدید", "active": "فعال", "banned": "مسدود"}
        if lang == "fa"
        else {"total": "Total", "new": "New", "active": "Active", "banned": "Banned"}
    )
    add_section(
        labels["users"],
        [(user_labels[key], users.get(key, 0)) for key in ("total", "new", "active", "banned")]
        + [(labels["wallet"], report.get("wallet_total", 0))],
    )

    order_rows = list((report.get("orders_by_status") or {}).items())
    order_rows.append((labels["revenue"], report.get("delivered_revenue", 0)))
    add_section(labels["orders"], order_rows)

    top_products = report.get("top_products") or []
    if top_products:
        add_section(
            labels["top"],
            [
                (
                    f"{row['product']} ({row['sales']})",
                    row["revenue"],
                )
                for row in top_products
            ],
        )

    transaction_rows = list((report.get("transactions_by_status") or {}).items())
    transaction_rows.extend(
        (f"success {row['currency']}", row["total"])
        for row in (report.get("transaction_totals") or [])
    )
    add_section(labels["transactions"], transaction_rows or [("—", 0)])
    add_section(
        labels["cashouts"],
        list((report.get("cashouts_by_status") or {}).items()) or [("—", 0)],
    )

    catalog = report.get("catalog") or {}
    catalog_labels = (
        {
            "active_products": "محصول فعال",
            "active_plans": "پلن فعال",
            "sellable_stock": "موجودی قابل فروش",
            "low_stock_plans": "پلن کم‌موجود",
            "zero_stock_plans": "پلن ناموجود",
        }
        if lang == "fa"
        else {
            "active_products": "Active products",
            "active_plans": "Active plans",
            "sellable_stock": "Sellable stock",
            "low_stock_plans": "Low-stock plans",
            "zero_stock_plans": "Zero-stock plans",
        }
    )
    add_section(
        labels["catalog"],
        [(catalog_labels[key], catalog.get(key, 0)) for key in catalog_labels],
    )
    low_stock = report.get("low_stock_detail") or []
    if low_stock:
        add_section(
            labels["low"],
            [
                (f"{row['product']} — {row['plan']}", row["stock"])
                for row in low_stock
            ],
        )

    document.build(story)
    return output.getvalue()
