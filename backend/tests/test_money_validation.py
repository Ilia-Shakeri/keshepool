from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api import payments
from app.core.money import DecimalValidationError, finite_decimal, quantized_decimal
from app.services import inventory_service, system_report_service, wallet_service


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", None, True])
def test_generic_decimal_parser_rejects_non_finite_or_non_numeric_values(value):
    with pytest.raises(DecimalValidationError):
        finite_decimal(value)


def test_quantized_decimal_enforces_storage_range():
    assert quantized_decimal("1.239", Decimal("0.01")) == Decimal("1.24")
    with pytest.raises(DecimalValidationError):
        quantized_decimal("11", Decimal("0.01"), maximum=Decimal("10"))


@pytest.mark.parametrize("parser", [wallet_service.to_decimal, inventory_service._money])
def test_wallet_money_paths_reject_non_finite_values(parser):
    with pytest.raises(DecimalValidationError):
        parser("NaN")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0", "-1", "1000000.000001"])
def test_crypto_amount_rejects_non_finite_and_non_positive_values(value):
    with pytest.raises(HTTPException) as raised:
        payments._usdt_amount(value)
    assert raised.value.status_code == 400


def test_report_number_keeps_decimal_without_float_rounding():
    value = Decimal("9007199254740993.25")
    assert system_report_service._number(value) == "9,007,199,254,740,993.25"
    assert system_report_service._number(Decimal("NaN")) == "—"
