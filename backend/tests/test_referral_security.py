from app.api.users import signed_referrer_telegram_id


def test_referrer_uses_only_bounded_signed_start_parameter() -> None:
    assert signed_referrer_telegram_id({"start_param": "ref_42"}) == "42"
    assert signed_referrer_telegram_id({"start_param": "ref_00042"}) is None
    assert signed_referrer_telegram_id({"start_param": "ref_-42"}) is None
    assert signed_referrer_telegram_id({"start_param": "ref_" + "9" * 21}) is None
    assert signed_referrer_telegram_id({"start_param": "bad_42"}) is None
    assert signed_referrer_telegram_id({}) is None
