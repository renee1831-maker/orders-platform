"""Definición de la tabla. Debe mantenerse alineada con infra/pipeline.yaml."""

from typing import Any

GSI_BY_CREATED_AT = "gsi_entity_created_at"
GSI_BY_STATUS = "gsi_status_created_at"


def create_orders_table(client: Any, table_name: str) -> None:
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "entity_type", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": GSI_BY_CREATED_AT,
                "KeySchema": [
                    {"AttributeName": "entity_type", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": GSI_BY_STATUS,
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )
    client.get_waiter("table_exists").wait(TableName=table_name)
