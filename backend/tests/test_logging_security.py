import json
import logging

from pythonjsonlogger import jsonlogger

from app.core.logging_security import REDACTED, SensitiveDataFilter, redact_log_text


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.items.append(json.loads(self.format(record)))


def test_redact_log_text_covers_common_secret_shapes() -> None:
    bot_token = "123456789:" + "x" * 35
    raw = (
        f"token={bot_token} authorization=Bearer-secret "
        "https://test.invalid/cb?signature=signed-value&ok=1"
    )
    scrubbed = redact_log_text(raw)
    assert bot_token not in scrubbed
    assert "Bearer-secret" not in scrubbed
    assert "signed-value" not in scrubbed
    assert scrubbed.count(REDACTED) >= 3


def test_filter_scrubs_message_args_and_structured_fields() -> None:
    logger = logging.getLogger("test.logging-security")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = _ListHandler()
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(jsonlogger.JsonFormatter())
    logger.addHandler(handler)

    logger.info(
        "request failed: %s",
        "credential=full-value",
        extra={
            "request_id": "safe-id",
            "callback_payload": {"secret": "hidden", "status": "bad"},
            "cashout_id": 44,
        },
    )

    item = handler.items[0]
    serialized = json.dumps(item)
    assert "full-value" not in serialized
    assert "hidden" not in serialized
    assert item["request_id"] == "safe-id"
    assert item["callback_payload"] == REDACTED
    assert item["cashout_id"] == 44
