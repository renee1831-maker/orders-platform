import threading

from app.domain.exceptions import ConcurrencyConflictError, InvalidCursorError, OrderNotFoundError
from app.domain.order import Order
from app.repositories.base import OrderPage, OrderQuery
from app.repositories.cursor import decode_cursor, encode_cursor


class InMemoryOrderRepository:
    """Implementación para pruebas y desarrollo local. No usar con múltiples procesos."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._lock = threading.Lock()

    def add(self, order: Order) -> None:
        with self._lock:
            if order.id in self._orders:
                raise ConcurrencyConflictError(order.id)
            self._orders[order.id] = order

    def get(self, order_id: str) -> Order | None:
        with self._lock:
            return self._orders.get(order_id)

    def update(self, order: Order, expected_version: int) -> None:
        with self._lock:
            current = self._orders.get(order.id)
            if current is None:
                raise OrderNotFoundError(order.id)
            if current.version != expected_version:
                raise ConcurrencyConflictError(order.id)
            self._orders[order.id] = order

    def find(self, query: OrderQuery) -> OrderPage:
        with self._lock:
            orders = list(self._orders.values())

        filtered = [
            o
            for o in orders
            if (query.status is None or o.status == query.status)
            and (query.created_from is None or o.created_at >= query.created_from)
            and (query.created_to is None or o.created_at <= query.created_to)
        ]
        filtered.sort(key=lambda o: (o.created_at, o.id), reverse=query.descending)

        offset = self._offset_from_cursor(query.cursor)
        end = offset + query.limit
        next_cursor = encode_cursor({"offset": str(end)}) if end < len(filtered) else None
        return OrderPage(items=tuple(filtered[offset:end]), next_cursor=next_cursor)

    def ping(self) -> bool:
        return True

    @staticmethod
    def _offset_from_cursor(cursor: str | None) -> int:
        if cursor is None:
            return 0
        data = decode_cursor(cursor)
        try:
            offset = int(data["offset"])
        except (KeyError, ValueError) as exc:
            raise InvalidCursorError() from exc
        if offset < 0:
            raise InvalidCursorError()
        return offset
