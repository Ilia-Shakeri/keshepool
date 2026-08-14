from decimal import Decimal, InvalidOperation
from typing import Any


class DecimalValidationError(ValueError):
    pass


def finite_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise DecimalValidationError("A finite decimal value is required.")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DecimalValidationError("A finite decimal value is required.") from exc
    if not parsed.is_finite():
        raise DecimalValidationError("A finite decimal value is required.")
    return parsed


def quantized_decimal(
    value: Any,
    quantum: Decimal,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal:
    parsed = finite_decimal(value)
    if minimum is not None and parsed < minimum:
        raise DecimalValidationError("Decimal value is below the allowed range.")
    if maximum is not None and parsed > maximum:
        raise DecimalValidationError("Decimal value exceeds the allowed range.")
    try:
        quantized = parsed.quantize(quantum)
    except InvalidOperation as exc:
        raise DecimalValidationError("Decimal precision exceeds the allowed range.") from exc
    if not quantized.is_finite():
        raise DecimalValidationError("A finite decimal value is required.")
    return quantized
