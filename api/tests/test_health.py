import pytest
from fastapi.testclient import TestClient

from ft.config import get_settings
from ft.main import create_app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_ok(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["env"] == "staging"


def test_docs_hidden_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_available_outside_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    client = TestClient(create_app())

    assert client.get("/openapi.json").status_code == 200
