from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import OrderServiceDep, require_api_key
from app.api.schemas import ErrorResponse, OrderCreate, OrderListOut, OrderOut, StatusUpdate
from app.domain.order import OrderStatus
from app.repositories.base import OrderQuery

router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
    responses={422: {"model": ErrorResponse}},
)

SortOption = Literal["created_at", "-created_at"]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    summary="Crear un pedido",
)
def create_order(payload: OrderCreate, response: Response, service: OrderServiceDep) -> OrderOut:
    order = service.create_order(payload.to_command())
    response.headers["Location"] = f"{router.prefix}/{order.id}"
    return OrderOut.model_validate(order)


@router.get("", summary="Listar pedidos con filtros, orden y paginación")
def list_orders(
    service: OrderServiceDep,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    sort: Annotated[SortOption, Query(description="'-' indica descendente")] = "-created_at",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
) -> OrderListOut:
    start, end = _as_utc(created_from), _as_utc(created_to)
    if start and end and start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="created_from debe ser anterior o igual a created_to.",
        )
    page = service.list_orders(
        OrderQuery(
            status=order_status,
            created_from=start,
            created_to=end,
            descending=sort.startswith("-"),
            limit=limit,
            cursor=cursor,
        )
    )
    items = [OrderOut.model_validate(order) for order in page.items]
    return OrderListOut(items=items, count=len(items), next_cursor=page.next_cursor)


@router.get("/{order_id}", summary="Obtener un pedido", responses={404: {"model": ErrorResponse}})
def get_order(order_id: UUID, service: OrderServiceDep) -> OrderOut:
    return OrderOut.model_validate(service.get_order(str(order_id)))


@router.patch(
    "/{order_id}/status",
    dependencies=[Depends(require_api_key)],
    summary="Actualizar el estado de un pedido",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_order_status(
    order_id: UUID, payload: StatusUpdate, service: OrderServiceDep
) -> OrderOut:
    order = service.update_status(str(order_id), payload.status, payload.note)
    return OrderOut.model_validate(order)
