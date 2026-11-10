#!/usr/bin/env python3
"""Smoke test post-despliegue. Solo usa la librería estándar (no requiere pip install).

Modos:
  read-only  -> health + listado (seguro para producción)
  full       -> además crea un pedido y recorre su ciclo de estados (staging)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

TIMEOUT_SECONDS = 10


class SmokeTestError(Exception):
    pass


def call(base: str, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = os.environ.get("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestError(message)
    print(f"  ✔ {message}")


def wait_until_healthy(base: str, attempts: int, delay: int) -> None:
    for attempt in range(1, attempts + 1):
        try:
            status, body = call(base, "GET", "/health")
            if status == 200 and body.get("status") == "ok":
                print(f"  ✔ /health OK (build {body.get('build', {}).get('commit', '?')[:8]})")
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            print(f"  … intento {attempt}/{attempts}: {exc}")
        time.sleep(delay)
    raise SmokeTestError(f"El servicio no respondió saludable tras {attempts} intentos.")


def read_only_checks(base: str) -> None:
    status, body = call(base, "GET", "/health/ready")
    expect(status == 200, "Readiness: persistencia accesible")
    status, body = call(base, "GET", "/api/v1/orders?limit=5")
    expect(status == 200 and "items" in body, "Listado de pedidos responde")


def write_checks(base: str) -> None:
    payload = {
        "customer": {"name": "Smoke Test", "email": "smoke@example.com"},
        "items": [
            {"sku": "SMOKE-1", "name": "Producto prueba", "quantity": 1, "unit_price": "1.00"}
        ],
        "shipping_address": {
            "street": "Calle 1 # 1-1",
            "city": "Bogotá",
            "state": "Cundinamarca",
            "postal_code": "110111",
            "country": "Colombia",
        },
    }
    status, order = call(base, "POST", "/api/v1/orders", payload)
    expect(status == 201 and order["status"] == "PENDING", "Crear pedido -> 201 PENDING")
    order_id = order["id"]

    status, fetched = call(base, "GET", f"/api/v1/orders/{order_id}")
    expect(status == 200 and fetched["id"] == order_id, "Consultar pedido por id")

    for target in ("IN_PROCESS", "SHIPPED", "DELIVERED"):
        path = f"/api/v1/orders/{order_id}/status"
        status, updated = call(base, "PATCH", path, {"status": target})
        expect(status == 200 and updated["status"] == target, f"Transición a {target}")

    status, _ = call(base, "PATCH", f"/api/v1/orders/{order_id}/status", {"status": "PENDING"})
    expect(status == 409, "Transición inválida rechazada con 409")

    status, listing = call(base, "GET", "/api/v1/orders?status=DELIVERED&limit=50")
    expect(
        status == 200 and any(o["id"] == order_id for o in listing["items"]),
        "Filtro por estado incluye el pedido",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--mode", choices=("read-only", "full"), default="read-only")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()

    # La consola de Windows usa cp1252 y no puede imprimir ✔/✘.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    base = args.url.rstrip("/")
    if urlparse(base).scheme not in ("http", "https"):
        print("La URL debe usar http o https.", file=sys.stderr)
        return 2

    print(f"Smoke test sobre {base} ({args.mode})")
    try:
        wait_until_healthy(base, args.attempts, args.delay)
        read_only_checks(base)
        if args.mode == "full":
            write_checks(base)
    except (SmokeTestError, KeyError, ValueError) as exc:
        print(f"  ✘ FALLÓ: {exc}", file=sys.stderr)
        return 1
    print("Smoke test superado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
