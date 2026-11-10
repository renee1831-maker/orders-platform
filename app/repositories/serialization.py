"""Mapeo entre la entidad de dominio y el ítem de DynamoDB."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.order import (
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    ShippingAddress,
    StatusChange,
)

ENTITY_TYPE = "ORDER"
# Formato fijo con microsegundos: el orden lexicográfico coincide con el cronológico,
# requisito para usarlo como sort key en los GSI.
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def to_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime(TIMESTAMP_FORMAT)


def from_timestamp(value: str) -> datetime:
    return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=UTC)


def order_to_item(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "entity_type": ENTITY_TYPE,
        "status": order.status.value,
        "created_at": to_timestamp(order.created_at),
        "updated_at": to_timestamp(order.updated_at),
        "version": order.version,
        "total": order.total,
        "customer": {
            "name": order.customer.name,
            "email": order.customer.email,
            "phone": order.customer.phone,
        },
        "items": [
            {
                "sku": item.sku,
                "name": item.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ],
        "shipping_address": {
            "street": order.shipping_address.street,
            "city": order.shipping_address.city,
            "state": order.shipping_address.state,
            "postal_code": order.shipping_address.postal_code,
            "country": order.shipping_address.country,
        },
        "status_history": [
            {
                "status": change.status.value,
                "changed_at": to_timestamp(change.changed_at),
                "note": change.note,
            }
            for change in order.status_history
        ],
    }


def item_to_order(item: dict[str, Any]) -> Order:
    customer = item["customer"]
    address = item["shipping_address"]
    return Order(
        id=str(item["id"]),
        customer=Customer(
            name=str(customer["name"]),
            email=str(customer["email"]),
            phone=customer.get("phone"),
        ),
        items=tuple(
            OrderItem(
                sku=str(i["sku"]),
                name=str(i["name"]),
                quantity=int(i["quantity"]),
                unit_price=Decimal(str(i["unit_price"])),
            )
            for i in item["items"]
        ),
        shipping_address=ShippingAddress(
            street=str(address["street"]),
            city=str(address["city"]),
            state=str(address["state"]),
            postal_code=str(address["postal_code"]),
            country=str(address["country"]),
        ),
        status=OrderStatus(item["status"]),
        created_at=from_timestamp(item["created_at"]),
        updated_at=from_timestamp(item["updated_at"]),
        status_history=tuple(
            StatusChange(
                status=OrderStatus(c["status"]),
                changed_at=from_timestamp(c["changed_at"]),
                note=c.get("note"),
            )
            for c in item["status_history"]
        ),
        version=int(item["version"]),
    )
