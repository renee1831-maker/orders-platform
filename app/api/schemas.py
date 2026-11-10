from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.domain.order import Customer, OrderItem, OrderStatus, ShippingAddress
from app.services.order_service import CreateOrderCommand

ShortText = Annotated[str, Field(min_length=2, max_length=120)]


class InputModel(BaseModel):
    # extra="forbid" evita mass-assignment (p. ej. que el cliente envíe "status" o "total").
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Entrada ----------
class CustomerIn(InputModel):
    name: ShortText
    email: EmailStr
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,20}$")


class OrderItemIn(InputModel):
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0, le=10_000)
    unit_price: Decimal = Field(gt=0, le=Decimal("1000000"), max_digits=12, decimal_places=2)


class ShippingAddressIn(InputModel):
    street: str = Field(min_length=3, max_length=200)
    city: ShortText
    state: ShortText
    postal_code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9 -]+$")
    country: str = Field(min_length=2, max_length=56)


class OrderCreate(InputModel):
    customer: CustomerIn
    items: list[OrderItemIn] = Field(min_length=1, max_length=100)
    shipping_address: ShippingAddressIn

    @model_validator(mode="after")
    def _unique_skus(self) -> "OrderCreate":
        skus = [item.sku for item in self.items]
        if len(skus) != len(set(skus)):
            raise ValueError("Cada SKU debe aparecer una sola vez; use 'quantity' para repetir.")
        return self

    def to_command(self) -> CreateOrderCommand:
        return CreateOrderCommand(
            customer=Customer(**self.customer.model_dump()),
            items=[OrderItem(**item.model_dump()) for item in self.items],
            shipping_address=ShippingAddress(**self.shipping_address.model_dump()),
        )


class StatusUpdate(InputModel):
    status: OrderStatus
    note: str | None = Field(default=None, max_length=500)


# ---------- Salida ----------
class CustomerOut(OutputModel):
    name: str
    email: str
    phone: str | None


class OrderItemOut(OutputModel):
    sku: str
    name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class ShippingAddressOut(OutputModel):
    street: str
    city: str
    state: str
    postal_code: str
    country: str


class StatusChangeOut(OutputModel):
    status: OrderStatus
    changed_at: datetime
    note: str | None


class OrderOut(OutputModel):
    id: str
    status: OrderStatus
    customer: CustomerOut
    items: list[OrderItemOut]
    shipping_address: ShippingAddressOut
    total: Decimal
    created_at: datetime
    updated_at: datetime
    status_history: list[StatusChangeOut]
    version: int


class OrderListOut(BaseModel):
    items: list[OrderOut]
    count: int
    next_cursor: str | None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
