from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
RepositoryBackend = Literal["memory", "dynamodb"]


class Settings(BaseSettings):
    """Configuración 12-factor: todo se lee de variables de entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "orders-api"
    app_env: Environment = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    enable_docs: bool = True

    repository_backend: RepositoryBackend = "memory"
    orders_table_name: str = "orders"
    aws_region: str = "us-east-1"
    dynamodb_endpoint_url: str | None = None

    # Si se define, las operaciones de escritura exigen el header X-API-Key.
    api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _forbid_memory_backend_in_cloud(self) -> "Settings":
        # Fail fast: con varios workers/instancias el backend en memoria pierde datos.
        if self.app_env in ("staging", "production") and self.repository_backend == "memory":
            raise ValueError("REPOSITORY_BACKEND=memory no está permitido en staging/production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
