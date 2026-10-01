import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from ft import auth
from ft.config import get_settings
from ft.main import create_app

SUPABASE_URL = "https://projetoteste.supabase.co"
USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER = "22222222-2222-2222-2222-222222222222"

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


def make_token(key=PRIVATE_KEY, algorithm="ES256", **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": USER_ID,
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + 3600,
        "aal": "aal2",
        "role": "authenticated",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=algorithm)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_JWKS_URL", f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    monkeypatch.setenv("ALLOWED_USER_IDS", USER_ID)
    get_settings.cache_clear()

    fake_jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=PRIVATE_KEY.public_key())
    )
    monkeypatch.setattr(auth, "_jwks_client", lambda _url: fake_jwks)

    yield TestClient(create_app())
    get_settings.cache_clear()


def get_me(client, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/me", headers=headers)


def test_valid_token_returns_user(client):
    response = get_me(client, make_token())
    assert response.status_code == 200
    assert response.json() == {"user_id": USER_ID, "aal": "aal2"}


def test_missing_token_rejected(client):
    assert get_me(client).status_code == 401


def test_session_without_2fa_rejected(client):
    assert get_me(client, make_token(aal="aal1")).status_code == 401


def test_user_outside_allowlist_rejected(client):
    assert get_me(client, make_token(sub=OTHER_USER)).status_code == 401


def test_empty_allowlist_rejects_everyone(client, monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "")
    get_settings.cache_clear()
    app_client = TestClient(create_app())
    assert get_me(app_client, make_token()).status_code == 401


def test_expired_token_rejected(client):
    past = int(time.time()) - 7200
    assert get_me(client, make_token(iat=past, exp=past + 60)).status_code == 401


def test_wrong_issuer_rejected(client):
    token = make_token(iss="https://outroprojeto.supabase.co/auth/v1")
    assert get_me(client, token).status_code == 401


def test_wrong_audience_rejected(client):
    assert get_me(client, make_token(aud="anon")).status_code == 401


def test_token_signed_by_other_key_rejected(client):
    assert get_me(client, make_token(key=OTHER_PRIVATE_KEY)).status_code == 401


def test_hs256_token_rejected(client):
    # Ataque de troca de algoritmo: token simétrico não pode ser aceito.
    token = make_token(key="segredo-qualquer-com-tamanho-suficiente-32b", algorithm="HS256")
    assert get_me(client, token).status_code == 401


def test_error_message_is_generic(client):
    response = get_me(client, make_token(aal="aal1"))
    assert response.json() == {"detail": "Não autorizado"}


def test_market_status_requires_auth(client):
    assert client.get("/market/status").status_code == 401
    assert client.get("/market/status", headers={"Authorization": "Bearer x"}).status_code == 401


def test_market_routes_require_auth(client):
    assert client.get("/market/assets").status_code == 401
    assert client.get("/market/candles/PETR4").status_code == 401


def test_candles_rejects_invalid_ticker(client):
    token = make_token()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/market/candles/petr4;drop", headers=headers).status_code == 422
    assert client.get("/market/candles/PETR4?range=10y", headers=headers).status_code == 422
