import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.domain.exceptions import InvalidCursorError
from app.repositories.cursor import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    data = {"id": "abc", "created_at": "2026-01-01T00:00:00.000000Z"}
    assert decode_cursor(encode_cursor(data)) == data


@pytest.mark.parametrize("cursor", ["%%%", "bm90LWpzb24", "WzEsMl0", "eyJhIjoxfQ", "ñ", "a" * 3000])
def test_invalid_cursors_are_rejected(cursor: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)


def test_memory_backend_forbidden_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", repository_backend="memory")
