from collections.abc import Iterator
from datetime import timedelta

import boto3
import pytest
from moto import mock_aws

from app.domain.exceptions import ConcurrencyConflictError, InvalidCursorError
from app.domain.order import OrderStatus
from app.repositories.base import OrderQuery
from app.repositories.cursor import encode_cursor
from app.repositories.dynamodb_repository import DynamoDbOrderRepository
from app.repositories.dynamodb_schema import create_orders_table
from tests.factories import BASE_TIME, make_order

TABLE = "orders-test"
REGION = "us-east-1"


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoDbOrderRepository]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        create_orders_table(boto3.client("dynamodb", region_name=REGION), TABLE)
        yield DynamoDbOrderRepository(TABLE, region=REGION)


def test_add_and_get_round_trip(repo: DynamoDbOrderRepository) -> None:
    order = make_order()
    repo.add(order)
    assert repo.get(order.id) == order


def test_get_missing_returns_none(repo: DynamoDbOrderRepository) -> None:
    assert repo.get("missing") is None


def test_add_duplicate_id_conflicts(repo: DynamoDbOrderRepository) -> None:
    order = make_order()
    repo.add(order)
    with pytest.raises(ConcurrencyConflictError):
        repo.add(order)


def test_optimistic_locking(repo: DynamoDbOrderRepository) -> None:
    order = make_order()
    repo.add(order)
    updated = order.transition_to(OrderStatus.IN_PROCESS, now=BASE_TIME)

    repo.update(updated, expected_version=1)
    with pytest.raises(ConcurrencyConflictError):
        repo.update(updated, expected_version=1)
    assert repo.get(order.id) == updated


def test_find_sorted_filtered_and_paginated(repo: DynamoDbOrderRepository) -> None:
    orders = [make_order(now=BASE_TIME + timedelta(minutes=i)) for i in range(5)]
    for order in orders:
        repo.add(order)
    shipped = orders[2].transition_to(OrderStatus.IN_PROCESS, now=BASE_TIME)
    repo.update(shipped, expected_version=1)

    desc = repo.find(OrderQuery(limit=10))
    assert [o.id for o in desc.items] == [o.id for o in reversed(orders)]

    asc = repo.find(OrderQuery(descending=False, limit=10))
    assert [o.id for o in asc.items] == [o.id for o in orders]

    by_status = repo.find(OrderQuery(status=OrderStatus.IN_PROCESS))
    assert [o.id for o in by_status.items] == [orders[2].id]

    in_range = repo.find(
        OrderQuery(
            created_from=BASE_TIME + timedelta(minutes=1),
            created_to=BASE_TIME + timedelta(minutes=3),
            descending=False,
        )
    )
    assert [o.id for o in in_range.items] == [o.id for o in orders[1:4]]

    first_page = repo.find(OrderQuery(limit=2, descending=False))
    assert first_page.next_cursor is not None
    second_page = repo.find(OrderQuery(limit=2, descending=False, cursor=first_page.next_cursor))
    assert [o.id for o in second_page.items] == [o.id for o in orders[2:4]]


def test_find_with_foreign_cursor_is_rejected(repo: DynamoDbOrderRepository) -> None:
    repo.add(make_order())
    with pytest.raises(InvalidCursorError):
        repo.find(OrderQuery(cursor=encode_cursor({"foo": "bar"})))


def test_ping(repo: DynamoDbOrderRepository) -> None:
    assert repo.ping() is True


def test_cursor_from_other_index_is_rejected(repo: DynamoDbOrderRepository) -> None:
    for i in range(3):
        repo.add(make_order(now=BASE_TIME + timedelta(minutes=i)))
    page = repo.find(OrderQuery(limit=1))
    assert page.next_cursor is not None
    with pytest.raises(InvalidCursorError):
        repo.find(OrderQuery(status=OrderStatus.PENDING, cursor=page.next_cursor))
