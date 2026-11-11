from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.middleware import register_middleware
from app.api.routes import health, orders
from app.core.build_info import get_build_info
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.repositories.base import OrderRepository
from app.repositories.dynamodb_repository import DynamoDbOrderRepository
from app.repositories.memory_repository import InMemoryOrderRepository
from app.services.order_service import OrderService


def build_repository(settings: Settings) -> OrderRepository:
    if settings.repository_backend == "dynamodb":
        return DynamoDbOrderRepository(
            settings.orders_table_name,
            region=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
        )
    return InMemoryOrderRepository()


def create_app(
    settings: Settings | None = None, repository: OrderRepository | None = None
) -> FastAPI:
    """App factory: permite inyectar configuración y repositorio en pruebas."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Orders API.Plataforma 3 de Gestión de Pedidos",
        description="API REST de gestión de pedidos",
        version=get_build_info()["commit"],
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings
    app.state.order_service = OrderService(repository or build_repository(settings))

    register_middleware(app)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(orders.router)
    return app


app = create_app()
