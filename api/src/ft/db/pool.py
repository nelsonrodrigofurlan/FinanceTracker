"""Pool de conexões da API (evita reabrir conexão TLS com o Postgres a cada requisição)."""

from functools import lru_cache

from psycopg_pool import ConnectionPool

from ft.config import get_settings
from ft.db.connection import assert_db_matches_project


@lru_cache
def get_pool() -> ConnectionPool:
    settings = get_settings()
    assert_db_matches_project(settings)
    return ConnectionPool(
        settings.supabase_db_url,
        min_size=1,
        max_size=4,
        open=True,
        kwargs={"connect_timeout": 15, "application_name": "ft-api"},
        # Descarta conexões quebradas antes de entregar (rede/servidor pode ter caído).
        check=ConnectionPool.check_connection,
        name="ft-api",
    )


def close_pool() -> None:
    if get_pool.cache_info().currsize:
        get_pool().close()
        get_pool.cache_clear()
