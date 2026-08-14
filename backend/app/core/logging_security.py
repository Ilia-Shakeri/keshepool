import logging
import re
from collections.abc import Mapping
from typing import Any


REDACTED = "[REDACTED]"

_BOT_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])\d{6,12}:[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_LABELED_VALUE = re.compile(
    r"(?i)(\b(?:authorization|cookie|set-cookie|init[_-]?data|tgwebappdata|"
    r"password|passwd|credential(?:s)?|secret|token|api[_-]?key|signature|"
    r"cashout[_-]?details?)\b\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_QUERY_VALUE = re.compile(
    r"(?i)([?&](?:hash|token|secret|signature|key|credential|initData)=)[^&#\s]*"
)

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "credential",
    "init_data",
    "initdata",
    "password",
    "payload",
    "private_key",
    "secret",
    "signature",
    "token",
)

_STANDARD_LOG_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__)


def redact_log_text(value: object) -> str:
    text = str(value)
    text = _PRIVATE_KEY.sub(REDACTED, text)
    text = _BOT_TOKEN.sub(REDACTED, text)
    text = _LABELED_VALUE.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    return _QUERY_VALUE.sub(lambda match: f"{match.group(1)}{REDACTED}", text)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_log_value(value: Any, *, key: object | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_log_value(child_value, key=child_key)
            for child_key, child_value in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_log_value(child) for child in value)
    if isinstance(value, list):
        return [redact_log_value(child) for child in value]
    if isinstance(value, str):
        return redact_log_text(value)
    return value


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = redact_log_text(rendered)
        record.args = ()
        for key, value in list(record.__dict__.items()):
            if key in _STANDARD_LOG_RECORD_KEYS or key in {"msg", "args", "message"}:
                continue
            record.__dict__[key] = redact_log_value(value, key=key)
        return True
