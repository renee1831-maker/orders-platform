from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from app.repositories.memory_repository import InMemoryOrderRepository
from tests.factories import order_payload

BASE = "/api/v1/orders"


def _create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(BASE, json=order_payload(**overrides))
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


# ---------- Health ----------
def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Request-ID" in response.headers


def test_readiness(client: TestClient) -> None:
    assert client.get("/health/ready").json() == {"status": "ready"}


# ---------- Crear ----------
def test_create_order_returns_201_with_location(client: TestClient) -> None:
    response = client.post(BASE, json=order_payload())

    body = response.json()
    assert response.status_code == 201
    assert response.headers["Location"] == f"{BASE}/{body['id']}"
    assert body["status"] == "PENDING"
    assert body["total"] == "125.50"
    assert body["items"][0]["subtotal"] == "100.00"


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"items": []}, "body.items"),
        ({"customer": {"name": "Ana", "email": "no-es-email"}}, "body.customer.email"),
        ({"status": "DELIVERED"}, "body.status"),
        (
            {"items": [{"sku": "A", "name": "x", "quantity": 0, "unit_price": "1.00"}]},
            "body.items.0.quantity",
        ),
        (
            {"items": [{"sku": "A", "name": "x", "quantity": 1, "unit_price": "1.001"}]},
            "body.items.0.unit_price",
        ),
        (
            {"items": [{"sku": "A B", "name": "x", "quantity": 1, "unit_price": "1.00"}]},
            "body.items.0.sku",
        ),
    ],
)
def test_create_order_validation(client: TestClient, override: dict[str, Any], field: str) -> None:
    response = client.post(BASE, json=order_payload(**override))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(d["field"].startswith(field) for d in error["details"])


def test_duplicate_skus_are_rejected(client: TestClient) -> None:
    item = {"sku": "A", "name": "x", "quantity": 1, "unit_price": "1.00"}
    response = client.post(BASE, json=order_payload(items=[item, item]))
    assert response.status_code == 422


# ---------- Consultar ----------
def test_get_order(client: TestClient) -> None:
    created = _create(client)
    response = client.get(f"{BASE}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_order_returns_404(client: TestClient) -> None:
    response = client.get(f"{BASE}/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_get_with_invalid_uuid_returns_422(client: TestClient) -> None:
    assert client.get(f"{BASE}/not-a-uuid").status_code == 422


def test_list_sorted_desc_by_default_and_asc_on_request(client: TestClient) -> None:
    ids = [_create(client)["id"] for _ in range(3)]

    desc = client.get(BASE).json()
    asc = client.get(BASE, params={"sort": "created_at"}).json()

    assert [o["id"] for o in desc["items"]] == list(reversed(ids))
    assert [o["id"] for o in asc["items"]] == ids


def test_list_filter_by_status(client: TestClient) -> None:
    first = _create(client)
    _create(client)
    client.patch(f"{BASE}/{first['id']}/status", json={"status": "IN_PROCESS"})

    body = client.get(BASE, params={"status": "IN_PROCESS"}).json()

    assert body["count"] == 1
    assert body["items"][0]["id"] == first["id"]


def test_list_filter_by_date_range(client: TestClient) -> None:
    orders = [_create(client) for _ in range(3)]
    params = {"created_from": orders[1]["created_at"], "created_to": orders[1]["created_at"]}

    body = client.get(BASE, params=params).json()

    assert [o["id"] for o in body["items"]] == [orders[1]["id"]]


def test_list_rejects_inverted_date_range(client: TestClient) -> None:
    params = {"created_from": "2026-02-01T00:00:00Z", "created_to": "2026-01-01T00:00:00Z"}
    assert client.get(BASE, params=params).status_code == 422


def test_list_pagination(client: TestClient) -> None:
    for _ in range(5):
        _create(client)

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = client.get(BASE, params=params).json()
        seen.extend(o["id"] for o in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == len(set(seen)) == 5


def test_list_with_invalid_cursor_returns_400(client: TestClient) -> None:
    response = client.get(BASE, params={"cursor": "basura"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


# ---------- Actualizar estado ----------
def test_update_status_full_flow(client: TestClient) -> None:
    order_id = _create(client)["id"]

    for target in ("IN_PROCESS", "SHIPPED", "DELIVERED"):
        response = client.patch(f"{BASE}/{order_id}/status", json={"status": target})
        assert response.status_code == 200
        assert response.json()["status"] == target

    history = client.get(f"{BASE}/{order_id}").json()["status_history"]
    assert [h["status"] for h in history] == ["PENDING", "IN_PROCESS", "SHIPPED", "DELIVERED"]


def test_invalid_transition_returns_409(client: TestClient) -> None:
    order_id = _create(client)["id"]

    response = client.patch(f"{BASE}/{order_id}/status", json={"status": "DELIVERED"})

    error = response.json()["error"]
    assert response.status_code == 409
    assert error["code"] == "INVALID_STATUS_TRANSITION"
    assert error["details"]["allowed"] == ["IN_PROCESS"]


def test_unknown_status_value_returns_422(client: TestClient) -> None:
    order_id = _create(client)["id"]
    response = client.patch(f"{BASE}/{order_id}/status", json={"status": "LOST"})
    assert response.status_code == 422


# ---------- API key opcional ----------
def test_api_key_is_enforced_on_writes_when_configured() -> None:
    settings = Settings(app_env="test", api_key=SecretStr("s3cret"), log_level="WARNING")
    app = create_app(settings=settings, repository=InMemoryOrderRepository())
    with TestClient(app) as client:
        assert client.post(BASE, json=order_payload()).status_code == 401
        wrong = client.post(BASE, json=order_payload(), headers={"X-API-Key": "nope"})
        assert wrong.status_code == 401
        ok = client.post(BASE, json=order_payload(), headers={"X-API-Key": "s3cret"})
        assert ok.status_code == 201
        # Las lecturas siguen abiertas.
        assert client.get(BASE).status_code == 200
