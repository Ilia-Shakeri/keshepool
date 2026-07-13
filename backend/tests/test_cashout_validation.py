import pytest
from pydantic import ValidationError

from app.api.cashout import CashoutRequestCreate


def test_other_cashout_platform_requires_custom_source_even_when_field_is_omitted():
    with pytest.raises(ValidationError, match="custom_source"):
        CashoutRequestCreate(
            source_platform="other",
            details_text="Valid request details",
        )


def test_cashout_details_reject_whitespace_and_normalize_valid_text():
    with pytest.raises(ValidationError, match="non-space"):
        CashoutRequestCreate(
            source_platform="wise",
            details_text="          ",
        )

    payload = CashoutRequestCreate(
        source_platform="other",
        custom_source="  Local platform  ",
        details_text="  Valid request details  ",
    )
    assert payload.custom_source == "Local platform"
    assert payload.details_text == "Valid request details"
