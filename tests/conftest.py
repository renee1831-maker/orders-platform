from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.memory_repository import InMemoryOrderRepository
from app.services.order_service import OrderService
from tests.factories import FakeClock


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", repository_backend="memory", log_level="WARNING")


@pytest.fixture
def repository() -> InMemoryOrderRepository:
    return InMemoryOrderRepository()


@pytest.fixture
def service(repository: InMemoryOrderRepository) -> OrderService:
    return OrderService(repository, clock=FakeClock())


@pytest.fixture
def client(settings: Settings, repository: InMemoryOrderRepository) -> Iterator[TestClient]:
    app = create_app(settings=settings, repository=repository)
    app.state.order_service = OrderService(repository, clock=FakeClock())
    with TestClient(app) as test_client:
        yield test_client
