from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from app.domain.exceptions import InvalidOrderError, InvalidStatusTransitionError


class OrderStatus(StrEnum):
    PENDING = "PENDING"  # Pendiente
    IN_PROCESS = "IN_PROCESS"  # En proceso
    SHIPPED = "SHIPPED"  # Enviado
    DELIVERED = "DELIVERED"  # Entregado


# Máquina de estados: el flujo es lineal y no permite retrocesos.
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.IN_PROCESS}),
    OrderStatus.IN_PROCESS: frozenset({OrderStatus.SHIPPED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Customer:
    name: str
    email: str
    phone: str | None = None


@dataclass(frozen=True, slots=True)
class OrderItem:
    sku: str
    name: str
    quantity: int
    unit_price: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass(frozen=True, slots=True)
class ShippingAddress:
    street: str
    city: str
    state: str
    postal_code: str
    country: str


@dataclass(frozen=True, slots=True)
class StatusChange:
    status: OrderStatus
    changed_at: datetime
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    customer: Customer
    items: tuple[OrderItem, ...]
    shipping_address: ShippingAddress
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    status_history: tuple[StatusChange, ...]
    version: int = 1

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items), start=Decimal("0"))

    @classmethod
    def create(
        cls,
        *,
        customer: Customer,
        items: Sequence[OrderItem],
        shipping_address: ShippingAddress,
        now: datetime,
    ) -> Order:
        if not items:
            raise InvalidOrderError("Un pedido debe contener al menos un producto.")
        if now.tzinfo is None:
            raise InvalidOrderError("La fecha de creación debe incluir zona horaria.")
        return cls(
            id=str(uuid4()),
            customer=customer,
            items=tuple(items),
            shipping_address=shipping_address,
            status=OrderStatus.PENDING,
            created_at=now,
            updated_at=now,
            status_history=(StatusChange(OrderStatus.PENDING, now, "Pedido creado"),),
            version=1,
        )

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        return new_status in ALLOWED_TRANSITIONS[self.status]

    def transition_to(
        self, new_status: OrderStatus, *, now: datetime, note: str | None = None
    ) -> Order:
        if not self.can_transition_to(new_status):
            raise InvalidStatusTransitionError(
                self.status.value,
                new_status.value,
                (s.value for s in ALLOWED_TRANSITIONS[self.status]),
            )
        return replace(
            self,
            status=new_status,
            updated_at=now,
            status_history=(*self.status_history, StatusChange(new_status, now, note)),
            version=self.version + 1,
        )
