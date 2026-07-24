from app.services.system_report_service import make_system_report_pdf


SAMPLE_REPORT = {
    "users": {"total": 10, "new": 2, "active": 7, "banned": 1},
    "wallet_total": 125000,
    "orders_by_status": {"active": 4, "refunded": 1},
    "delivered_revenue": 90000,
    "top_products": [{"product": "Service", "sales": 4, "revenue": 90000}],
    "transactions_by_status": {"success": 3, "pending": 1},
    "transaction_totals": [{"currency": "IRR", "total": 125000}],
    "cashouts_by_status": {"pending": 2},
    "catalog": {
        "active_products": 3,
        "active_plans": 5,
        "sellable_stock": 12,
        "low_stock_plans": 2,
        "zero_stock_plans": 1,
    },
    "low_stock_detail": [{"product": "Service", "plan": "1 month", "stock": 0}],
}


def test_full_report_pdf_starts_with_pdf_header_in_english():
    output = make_system_report_pdf(
        SAMPLE_REPORT,
        start_label="2026-07-01",
        end_label="2026-07-25",
        lang="en",
    )
    assert output.startswith(b"%PDF")


def test_full_report_pdf_starts_with_pdf_header_in_persian():
    output = make_system_report_pdf(
        SAMPLE_REPORT,
        start_label="2026-07-01",
        end_label="2026-07-25",
        lang="fa",
    )
    assert output.startswith(b"%PDF")
