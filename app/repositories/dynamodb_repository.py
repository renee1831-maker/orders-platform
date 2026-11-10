import logging
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, ConditionBase, Key
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.domain.exceptions import ConcurrencyConflictError, InvalidCursorError
from app.domain.order import Order
from app.repositories.base import OrderPage, OrderQuery
from app.repositories.cursor import decode_cursor, encode_cursor
from app.repositories.dynamodb_schema import GSI_BY_CREATED_AT, GSI_BY_STATUS
from app.repositories.serialization import (
    ENTITY_TYPE,
    item_to_order,
    order_to_item,
    to_timestamp,
)

logger = logging.getLogger(__name__)

_BOTO_CONFIG = Config(
    retries={"max_attempts": 5, "mode": "adaptive"},
    connect_timeout=2,
    read_timeout=5,
)


def _is_conditional_failure(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


class DynamoDbOrderRepository:
    def __init__(
        self,
        table_name: str,
        *,
        region: str,
        endpoint_url: str | None = None,
        session: boto3.session.Session | None = None,
    ) -> None:
        resource = (session or boto3.session.Session()).resource(
            "dynamodb", region_name=region, endpoint_url=endpoint_url, config=_BOTO_CONFIG
        )
        self._table: Any = resource.Table(table_name)

    def add(self, order: Order) -> None:
        try:
            self._table.put_item(
                Item=order_to_item(order), ConditionExpression=Attr("id").not_exists()
            )
        except ClientError as exc:
            if _is_conditional_failure(exc):
                raise ConcurrencyConflictError(order.id) from exc
            raise

    def get(self, order_id: str) -> Order | None:
        response = self._table.get_item(Key={"id": order_id}, ConsistentRead=True)
        item = response.get("Item")
        return item_to_order(item) if item else None

    def update(self, order: Order, expected_version: int) -> None:
        try:
            self._table.put_item(
                Item=order_to_item(order),
                ConditionExpression=Attr("id").exists() & Attr("version").eq(expected_version),
            )
        except ClientError as exc:
            if _is_conditional_failure(exc):
                raise ConcurrencyConflictError(order.id) from exc
            raise

    def find(self, query: OrderQuery) -> OrderPage:
        # Query sobre GSI (nunca Scan): costo proporcional a la página, no a la tabla.
        if query.status is not None:
            index_name = GSI_BY_STATUS
            key_condition: ConditionBase = Key("status").eq(query.status.value)
            partition_attr = "status"
        else:
            index_name = GSI_BY_CREATED_AT
            key_condition = Key("entity_type").eq(ENTITY_TYPE)
            partition_attr = "entity_type"

        range_condition = self._created_at_condition(query)
        if range_condition is not None:
            key_condition = key_condition & range_condition

        kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": not query.descending,
            "Limit": query.limit,
        }
        if query.cursor:
            start_key = decode_cursor(query.cursor)
            # El cursor debe pertenecer al mismo índice; si no, es manipulado o de otra consulta.
            if set(start_key) != {"id", "created_at", partition_attr}:
                raise InvalidCursorError()
            kwargs["ExclusiveStartKey"] = start_key

        try:
            response = self._table.query(**kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if query.cursor and code == "ValidationException":
                raise InvalidCursorError() from exc
            raise

        items = tuple(item_to_order(item) for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        next_cursor = encode_cursor({k: str(v) for k, v in last_key.items()}) if last_key else None
        return OrderPage(items=items, next_cursor=next_cursor)

    def ping(self) -> bool:
        try:
            self._table.load()
        except (ClientError, BotoCoreError):
            logger.exception("dynamodb_ping_failed")
            return False
        return True

    @staticmethod
    def _created_at_condition(query: OrderQuery) -> ConditionBase | None:
        created_at = Key("created_at")
        if query.created_from and query.created_to:
            return created_at.between(
                to_timestamp(query.created_from), to_timestamp(query.created_to)
            )
        if query.created_from:
            return created_at.gte(to_timestamp(query.created_from))
        if query.created_to:
            return created_at.lte(to_timestamp(query.created_to))
        return None
