import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.exceptions import OrderNotFoundError
from app.domain.order import Customer, Order, OrderItem, OrderStatus, ShippingAddress
from app.repositories.base import OrderPage, OrderQuery, OrderRepository

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    customer: Customer
    items: Sequence[OrderItem]
    shipping_address: ShippingAddress


class OrderService:
    """Casos de uso. Depende de la abstracción OrderRepository (DIP)."""

    def __init__(self, repository: OrderRepository, clock: Clock = utc_now) -> None:
        self._repository = repository
        self._clock = clock

    def create_order(self, command: CreateOrderCommand) -> Order:
        order = Order.create(
            customer=command.customer,
            items=command.items,
            shipping_address=command.shipping_address,
            now=self._clock(),
        )
        self._repository.add(order)
        logger.info(
            "order_created",
            extra={"extra_fields": {"order_id": order.id, "total": str(order.total)}},
        )
        return order

    def get_order(self, order_id: str) -> Order:
        order = self._repository.get(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    def list_orders(self, query: OrderQuery) -> OrderPage:
        return self._repository.find(query)

    def update_status(
        self, order_id: str, new_status: OrderStatus, note: str | None = None
    ) -> Order:
        current = self.get_order(order_id)
        updated = current.transition_to(new_status, now=self._clock(), note=note)
        self._repository.update(updated, expected_version=current.version)
        logger.info(
            "order_status_updated",
            extra={
                "extra_fields": {
                    "order_id": order_id,
                    "from_status": current.status.value,
                    "to_status": new_status.value,
                }
            },
        )
        return updated

    def is_healthy(self) -> bool:
        return self._repository.ping()
