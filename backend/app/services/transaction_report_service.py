from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_NAME = "DejaVuSans"
FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _register_font() -> None:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))


def _display(value: object, lang: str) -> str:
    text = str(value if value is not None else "—")
    if lang == "fa":
        text = get_display(arabic_reshaper.reshape(text))
    return escape(text)


def make_transaction_pdf(
    rows: list[dict[str, object]],
    *,
    start_label: str,
    end_label: str,
    lang: str,
) -> bytes:
    _register_font()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Keshepool transaction report",
    )
    alignment = TA_RIGHT if lang == "fa" else TA_LEFT
    normal = ParagraphStyle(
        "TransactionReport",
        fontName=FONT_NAME,
        fontSize=7.5,
        leading=10,
        alignment=alignment,
    )
    title_style = ParagraphStyle(
        "TransactionReportTitle",
        parent=normal,
        fontSize=13,
        leading=18,
    )
    labels = (
        ["ردیف", "زمان", "کاربر", "نوع", "وضعیت", "مبلغ", "ارز", "درگاه"]
        if lang == "fa"
        else ["ID", "Date", "User", "Type", "Status", "Amount", "Currency", "Gateway"]
    )
    title = (
        f"گزارش تراکنش‌ها از {start_label} تا {end_label}"
        if lang == "fa"
        else f"Transaction report from {start_label} to {end_label}"
    )
    story = [Paragraph(_display(title, lang), title_style), Spacer(1, 5 * mm)]
    table_data = [[Paragraph(_display(label, lang), normal) for label in labels]]
    for row in rows:
        table_data.append(
            [
                Paragraph(_display(row.get("id"), lang), normal),
                Paragraph(_display(row.get("date"), lang), normal),
                Paragraph(_display(row.get("user"), lang), normal),
                Paragraph(_display(row.get("type"), lang), normal),
                Paragraph(_display(row.get("status"), lang), normal),
                Paragraph(_display(row.get("amount"), lang), normal),
                Paragraph(_display(row.get("currency"), lang), normal),
                Paragraph(_display(row.get("gateway"), lang), normal),
            ]
        )

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[14 * mm, 31 * mm, 47 * mm, 32 * mm, 28 * mm, 34 * mm, 20 * mm, 32 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E63946")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#999999")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return output.getvalue()
