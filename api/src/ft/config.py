from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (no Cloud Run, vindas do Secret Manager).

    Localmente lê o `.env` da raiz do repositório (rodando a partir de `api/`).
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    supabase_url: str = ""
    supabase_jwks_url: str = ""
    supabase_project_ref: str = ""
    supabase_db_url: str = ""
    # IDs (UUID) de usuários autorizados, separados por vírgula. Vazio = ninguém (fail-closed).
    allowed_user_ids: Annotated[frozenset[str], NoDecode] = frozenset()

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(v.strip() for v in value.split(",") if v.strip())
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def expose_docs(self) -> bool:
        # Swagger/OpenAPI só fora de produção: não publicar o mapa da API.
        return not self.is_production

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
