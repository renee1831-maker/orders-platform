from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidOrderError, InvalidStatusTransitionError
from app.domain.order import OrderStatus
from tests.factories import BASE_TIME, make_order


def test_new_order_starts_pending_with_history() -> None:
    order = make_order()

    assert order.status is OrderStatus.PENDING
    assert order.version == 1
    assert len(order.status_history) == 1
    assert order.status_history[0].status is OrderStatus.PENDING


def test_total_is_sum_of_subtotals() -> None:
    assert make_order().total == Decimal("125.50")


def test_order_without_items_is_rejected() -> None:
    with pytest.raises(InvalidOrderError):
        make_order(items=[])


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(InvalidOrderError):
        make_order(now=datetime(2026, 1, 1))  # noqa: DTZ001


def test_full_lifecycle_transitions() -> None:
    order = make_order()
    later = BASE_TIME
    for target in (OrderStatus.IN_PROCESS, OrderStatus.SHIPPED, OrderStatus.DELIVERED):
        later += timedelta(minutes=1)
        order = order.transition_to(target, now=later, note=f"-> {target}")

    assert order.status is OrderStatus.DELIVERED
    assert order.version == 4
    assert [c.status for c in order.status_history] == list(OrderStatus)
    assert order.updated_at == later


@pytest.mark.parametrize(
    ("steps", "target"),
    [
        ([], OrderStatus.SHIPPED),
        ([], OrderStatus.PENDING),
        ([OrderStatus.IN_PROCESS], OrderStatus.PENDING),
        ([OrderStatus.IN_PROCESS, OrderStatus.SHIPPED, OrderStatus.DELIVERED], OrderStatus.SHIPPED),
    ],
)
def test_invalid_transitions_are_rejected(steps: list[OrderStatus], target: OrderStatus) -> None:
    order = make_order()
    for step in steps:
        order = order.transition_to(step, now=BASE_TIME)

    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        order.transition_to(target, now=BASE_TIME)
    assert exc_info.value.requested == target.value


def test_transition_does_not_mutate_original() -> None:
    order = make_order()
    order.transition_to(OrderStatus.IN_PROCESS, now=BASE_TIME)
    assert order.status is OrderStatus.PENDING
