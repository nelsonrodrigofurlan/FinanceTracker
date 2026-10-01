from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (no Cloud Run, vindas do Secret Manager)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def expose_docs(self) -> bool:
        # Swagger/OpenAPI só fora de produção: não publicar o mapa da API.
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
