import pytest

from app.domain.exceptions import ConcurrencyConflictError, OrderNotFoundError
from app.domain.order import OrderStatus
from app.repositories.base import OrderQuery
from app.repositories.memory_repository import InMemoryOrderRepository
from app.services.order_service import CreateOrderCommand, OrderService
from tests.factories import make_order


def _command() -> CreateOrderCommand:
    template = make_order()
    return CreateOrderCommand(
        customer=template.customer,
        items=template.items,
        shipping_address=template.shipping_address,
    )


def test_create_and_get_order(service: OrderService) -> None:
    created = service.create_order(_command())
    assert service.get_order(created.id) == created


def test_get_unknown_order_raises(service: OrderService) -> None:
    with pytest.raises(OrderNotFoundError):
        service.get_order("does-not-exist")


def test_update_status_persists_new_version(service: OrderService) -> None:
    created = service.create_order(_command())

    updated = service.update_status(created.id, OrderStatus.IN_PROCESS, "Alistando")

    assert updated.version == 2
    assert service.get_order(created.id).status is OrderStatus.IN_PROCESS
    assert updated.status_history[-1].note == "Alistando"


def test_list_orders_delegates_to_repository(service: OrderService) -> None:
    service.create_order(_command())
    service.create_order(_command())
    assert len(service.list_orders(OrderQuery()).items) == 2


def test_concurrent_update_is_detected(repository: InMemoryOrderRepository) -> None:
    order = make_order()
    repository.add(order)
    first = order.transition_to(OrderStatus.IN_PROCESS, now=order.created_at)
    repository.update(first, expected_version=1)

    # Una segunda escritura basada en la versión vieja debe fallar.
    with pytest.raises(ConcurrencyConflictError):
        repository.update(first, expected_version=1)


def test_health_reports_repository_status(service: OrderService) -> None:
    assert service.is_healthy() is True
