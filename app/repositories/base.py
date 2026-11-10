from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.order import Order, OrderStatus


@dataclass(frozen=True, slots=True)
class OrderQuery:
    status: OrderStatus | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    descending: bool = True
    limit: int = 20
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class OrderPage:
    items: tuple[Order, ...]
    next_cursor: str | None


class OrderRepository(Protocol):
    """Puerto de persistencia (Clean Architecture): el servicio no conoce DynamoDB."""

    def add(self, order: Order) -> None: ...

    def get(self, order_id: str) -> Order | None: ...

    def find(self, query: OrderQuery) -> OrderPage: ...

    def update(self, order: Order, expected_version: int) -> None:
        """Persiste el pedido solo si la versión almacenada coincide (bloqueo optimista)."""
        ...

    def ping(self) -> bool: ...
