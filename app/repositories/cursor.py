import base64
import binascii
import json

from app.domain.exceptions import InvalidCursorError

MAX_CURSOR_LENGTH = 2048


def encode_cursor(data: dict[str, str]) -> str:
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, str]:
    if len(cursor) > MAX_CURSOR_LENGTH:
        raise InvalidCursorError()
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise InvalidCursorError() from exc
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise InvalidCursorError()
    return data
