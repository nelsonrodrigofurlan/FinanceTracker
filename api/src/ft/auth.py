"""Autenticação da API: valida o JWT emitido pelo Supabase Auth.

Regras (todas obrigatórias):
- assinatura ES256 conferida com a chave pública do JWKS do projeto;
- `iss` do projeto, `aud` = "authenticated", `exp` válido;
- `aal` = "aal2" (login concluído com 2FA);
- `sub` presente na allowlist (fail-closed: allowlist vazia bloqueia todos).
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ft.config import Settings, get_settings

logger = logging.getLogger("ft.auth")

ALGORITHMS = ["ES256"]
AUDIENCE = "authenticated"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    aal: str


@lru_cache
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300, timeout=10)


def _unauthorized() -> HTTPException:
    # Resposta sempre genérica: o motivo fica só no log do servidor.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str, settings: Settings) -> CurrentUser:
    if not settings.supabase_url or not settings.supabase_jwks_url:
        logger.error("auth: SUPABASE_URL/SUPABASE_JWKS_URL não configurados")
        raise _unauthorized()

    try:
        jwks = _jwks_client(settings.supabase_jwks_url)
        key = jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        logger.warning("auth: token rejeitado (%s)", type(exc).__name__)
        raise _unauthorized() from exc

    if claims.get("aal") != "aal2":
        logger.warning("auth: sessão sem 2FA (aal=%s)", claims.get("aal"))
        raise _unauthorized()

    user_id = claims["sub"]
    if user_id not in settings.allowed_user_ids:
        logger.warning("auth: usuário fora da allowlist")
        raise _unauthorized()

    return CurrentUser(user_id=user_id, aal=claims["aal"])


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    return verify_token(credentials.credentials, settings)
