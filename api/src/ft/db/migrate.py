"""Aplica as migrations SQL de `supabase/migrations/` em ordem, uma vez cada.

Uso (a partir de `api/`):
    uv run python -m ft.db.migrate              # aplica pendentes no banco do .env
    uv run python -m ft.db.migrate --status     # só lista
Produção exige APP_ENV=production E a flag --allow-production.
"""

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path

import psycopg

from ft.config import get_settings
from ft.db.connection import connect

logger = logging.getLogger("ft.migrate")

# No repositório: <raiz>/supabase/migrations. No contêiner: definido por FT_MIGRATIONS_DIR.
MIGRATIONS_DIR = Path(
    os.environ.get(
        "FT_MIGRATIONS_DIR",
        Path(__file__).resolve().parents[4] / "supabase" / "migrations",
    )
)

BOOTSTRAP = """
create schema if not exists ft;
create table if not exists ft.schema_migrations (
    version     text primary key,
    checksum    text not null,
    applied_at  timestamptz not null default now()
);
revoke all on ft.schema_migrations from public;
"""


def list_migrations(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"))


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied_versions(conn: psycopg.Connection) -> dict[str, str]:
    rows = conn.execute("select version, checksum from ft.schema_migrations").fetchall()
    return {version: digest for version, digest in rows}


def run(status_only: bool, allow_production: bool) -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")

    if settings.is_production and not allow_production:
        logger.error("Recusado: APP_ENV=production exige --allow-production.")
        return 2

    migrations = list_migrations()
    if not migrations:
        logger.error("Nenhuma migration encontrada em %s", MIGRATIONS_DIR)
        return 4
    with connect(settings) as conn:
        conn.execute(BOOTSTRAP)
        conn.commit()
        done = applied_versions(conn)

        for path in migrations:
            version = path.stem
            digest = checksum(path)
            if version in done:
                if done[version] != digest:
                    logger.error(
                        "Migration %s foi alterada depois de aplicada. Abortando.", version
                    )
                    return 3
                logger.info("  ok        %s", version)
                continue
            if status_only:
                logger.info("  pendente  %s", version)
                continue
            logger.info("  aplicando %s ...", version)
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    "insert into ft.schema_migrations (version, checksum) values (%s, %s)",
                    (version, digest),
                )
            logger.info("  aplicada  %s", version)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="apenas lista o estado")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    sys.exit(run(status_only=args.status, allow_production=args.allow_production))


if __name__ == "__main__":
    main()
