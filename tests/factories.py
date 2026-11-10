from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.domain.order import Customer, Order, OrderItem, ShippingAddress

BASE_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    """Reloj determinista: cada llamada avanza un segundo."""

    def __init__(self, start: datetime = BASE_TIME) -> None:
        self._current = start

    def __call__(self) -> datetime:
        value = self._current
        self._current += timedelta(seconds=1)
        return value


def make_order(now: datetime = BASE_TIME, **overrides: Any) -> Order:
    params: dict[str, Any] = {
        "customer": Customer(name="Ana Gómez", email="ana@example.com", phone="+57 3001234567"),
        "items": [
            OrderItem(sku="SKU-1", name="Teclado", quantity=2, unit_price=Decimal("50.00")),
            OrderItem(sku="SKU-2", name="Mouse", quantity=1, unit_price=Decimal("25.50")),
        ],
        "shipping_address": ShippingAddress(
            street="Calle 100 # 10-20",
            city="Bogotá",
            state="Cundinamarca",
            postal_code="110111",
            country="Colombia",
        ),
        "now": now,
    }
    params.update(overrides)
    return Order.create(**params)


def order_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "customer": {"name": "Ana Gómez", "email": "ana@example.com", "phone": "+57 3001234567"},
        "items": [
            {"sku": "SKU-1", "name": "Teclado", "quantity": 2, "unit_price": "50.00"},
            {"sku": "SKU-2", "name": "Mouse", "quantity": 1, "unit_price": "25.50"},
        ],
        "shipping_address": {
            "street": "Calle 100 # 10-20",
            "city": "Bogotá",
            "state": "Cundinamarca",
            "postal_code": "110111",
            "country": "Colombia",
        },
    }
    payload.update(overrides)
    return payload
