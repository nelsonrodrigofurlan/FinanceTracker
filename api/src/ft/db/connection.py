from urllib.parse import urlparse

import psycopg

from ft.config import Settings, get_settings


class DatabaseConfigError(RuntimeError):
    pass


def assert_db_matches_project(settings: Settings) -> None:
    """Trava de segurança: a URL do banco precisa ser do mesmo projeto Supabase configurado."""
    if not settings.supabase_db_url:
        raise DatabaseConfigError("SUPABASE_DB_URL não configurada")
    if not settings.supabase_project_ref:
        raise DatabaseConfigError("SUPABASE_PROJECT_REF não configurado")
    parsed = urlparse(settings.supabase_db_url)
    target = f"{parsed.hostname or ''} {parsed.username or ''}"
    if settings.supabase_project_ref not in target:
        raise DatabaseConfigError(
            "SUPABASE_DB_URL não pertence ao SUPABASE_PROJECT_REF configurado"
        )


def connect(settings: Settings | None = None) -> psycopg.Connection:
    settings = settings or get_settings()
    assert_db_matches_project(settings)
    # prepare_threshold=None: compatível com o pooler do Supabase em modo transação (Cloud Run).
    return psycopg.connect(
        settings.supabase_db_url,
        connect_timeout=15,
        application_name="ft-api",
        prepare_threshold=None,
    )
