import secrets
from typing import Annotated, cast

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings
from app.services.order_service import OrderService


def get_settings_from_app(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_order_service(request: Request) -> OrderService:
    return cast(OrderService, request.app.state.order_service)


SettingsDep = Annotated[Settings, Depends(get_settings_from_app)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]


def require_api_key(
    settings: SettingsDep,
    x_api_key: Annotated[str | None, Header(max_length=256)] = None,
) -> None:
    """Protege escrituras solo si API_KEY está configurada (opt-in)."""
    if settings.api_key is None:
        return
    expected = settings.api_key.get_secret_value().encode("utf-8")
    provided = (x_api_key or "").encode("utf-8")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
