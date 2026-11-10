from collections.abc import Iterable


class DomainError(Exception):
    """Error base de la aplicación. Cada subclase define un código estable para la API."""

    code = "DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidOrderError(DomainError):
    code = "INVALID_ORDER"


class OrderNotFoundError(DomainError):
    code = "ORDER_NOT_FOUND"

    def __init__(self, order_id: str) -> None:
        super().__init__(f"El pedido '{order_id}' no existe.")
        self.order_id = order_id


class InvalidStatusTransitionError(DomainError):
    code = "INVALID_STATUS_TRANSITION"

    def __init__(self, current: str, requested: str, allowed: Iterable[str]) -> None:
        self.current = current
        self.requested = requested
        self.allowed = sorted(allowed)
        allowed_text = ", ".join(self.allowed) or "ninguno (estado final)"
        super().__init__(
            f"No se puede cambiar el estado de {current} a {requested}. "
            f"Estados permitidos: {allowed_text}."
        )


class ConcurrencyConflictError(DomainError):
    code = "CONCURRENCY_CONFLICT"

    def __init__(self, order_id: str) -> None:
        super().__init__(
            f"El pedido '{order_id}' fue modificado por otra operación. Vuelva a intentarlo."
        )
        self.order_id = order_id


class InvalidCursorError(DomainError):
    code = "INVALID_CURSOR"

    def __init__(self) -> None:
        super().__init__("El cursor de paginación es inválido o expiró.")
