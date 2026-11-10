"""Crea la tabla en DynamoDB Local (docker compose). Idempotente."""

import os

import boto3

from app.repositories.dynamodb_schema import create_orders_table


def main() -> None:
    table_name = os.environ.get("ORDERS_TABLE_NAME", "orders")
    client = boto3.client(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        endpoint_url=os.environ["DYNAMODB_ENDPOINT_URL"],
    )
    if table_name in client.list_tables()["TableNames"]:
        print(f"La tabla '{table_name}' ya existe.")
        return
    create_orders_table(client, table_name)
    print(f"Tabla '{table_name}' creada.")


if __name__ == "__main__":
    main()
