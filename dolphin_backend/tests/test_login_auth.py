import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.login_router import router as login_router
from api.dependencies import get_db_pool
from services.auth_service import DolphinAuthConnectionError
from models.user_models import User


class DummyPool:
    def __init__(self):
        self.fetchrow = AsyncMock(return_value=None)
        self.fetch = AsyncMock(return_value=[])
        self.fetchval = AsyncMock(return_value=0)
        self.execute = AsyncMock(return_value=None)

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setattr("config.settings.access_token_secret", "test-secret-" * 6)
    monkeypatch.setattr("config.settings.disable_external_auth", False)
    pool = DummyPool()
    app = FastAPI()
    app.include_router(login_router)
    app.dependency_overrides[get_db_pool] = lambda: pool
    with TestClient(app) as client:
        yield client, pool


def test_upstream_unreachable_dev_fallback_existing_user(auth_client, monkeypatch):
    client, pool = auth_client
    monkeypatch.setattr("config.settings.app_env", "development")

    dummy_user = User(
        id="dev-user-id",
        name="Test Dev",
        email="dev@example.com",
        role="Admin",
        role_id=1
    )

    with patch("services.auth_service.AuthService.authenticateDolphin", side_effect=DolphinAuthConnectionError("Timeout")):
        with patch("services.auth_service.AuthService.get_user_by_useremail", new_callable=AsyncMock, return_value=dummy_user):
            with patch("core.redis_client.redis_service.set_user_data", new_callable=AsyncMock):
                with patch("core.redis_client.redis_service.get_user_data", new_callable=AsyncMock, return_value={}):
                    resp = client.post("/login", json={"email": "dev@example.com", "password": "password123"})
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["email"] == "dev@example.com"
                    assert data["user_id"] == "dev-user-id"


def test_upstream_unreachable_dev_fallback_auto_create_new_user(auth_client, monkeypatch):
    client, pool = auth_client
    monkeypatch.setattr("config.settings.app_env", "development")

    created_user = User(
        id="new-user-id",
        name="Newuser",
        email="newuser@example.com",
        role="User",
        role_id=1
    )

    with patch("services.auth_service.AuthService.authenticateDolphin", side_effect=DolphinAuthConnectionError("Timeout")):
        with patch("services.auth_service.AuthService.get_user_by_useremail", new_callable=AsyncMock, side_effect=[None, created_user, created_user]):
            with patch("services.auth_service.AuthService.create_user", new_callable=AsyncMock, return_value=created_user):
                with patch("core.redis_client.redis_service.set_user_data", new_callable=AsyncMock):
                    with patch("core.redis_client.redis_service.get_user_data", new_callable=AsyncMock, return_value={}):
                        resp = client.post("/login", json={"email": "newuser@example.com", "password": "password123"})
                        assert resp.status_code == 200
                        data = resp.json()
                        assert data["email"] == "newuser@example.com"
                        assert data["user_id"] == "new-user-id"


def test_upstream_unreachable_in_production(auth_client, monkeypatch):
    client, pool = auth_client
    monkeypatch.setattr("config.settings.app_env", "production")

    with patch("services.auth_service.AuthService.authenticateDolphin", side_effect=DolphinAuthConnectionError("Timeout")):
        resp = client.post("/login", json={"email": "user@example.com", "password": "password123"})
        assert resp.status_code == 503
        assert "unreachable" in resp.json()["detail"].lower()


def test_disable_external_auth_bypasses_remote_call(auth_client, monkeypatch):
    client, pool = auth_client
    monkeypatch.setattr("config.settings.disable_external_auth", True)

    dummy_user = User(
        id="local-user-id",
        name="Local User",
        email="local@example.com",
        role="User",
        role_id=1
    )

    # authenticateDolphin should NOT even be called!
    with patch("services.auth_service.AuthService.authenticateDolphin") as mock_auth:
        with patch("services.auth_service.AuthService.get_user_by_useremail", new_callable=AsyncMock, return_value=dummy_user):
            with patch("core.redis_client.redis_service.set_user_data", new_callable=AsyncMock):
                with patch("core.redis_client.redis_service.get_user_data", new_callable=AsyncMock, return_value={}):
                    resp = client.post("/login", json={"email": "local@example.com", "password": "anypassword"})
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["email"] == "local@example.com"
                    assert data["user_id"] == "local-user-id"
                    mock_auth.assert_not_called()


def test_production_ignores_disable_external_auth_flag(auth_client, monkeypatch):
    """Even if disable_external_auth is True, production environment MUST call authenticateDolphin."""
    client, pool = auth_client
    monkeypatch.setattr("config.settings.app_env", "production")
    monkeypatch.setattr("config.settings.disable_external_auth", True)

    with patch("services.auth_service.AuthService.authenticateDolphin", side_effect=DolphinAuthConnectionError("Timeout")) as mock_auth:
        resp = client.post("/login", json={"email": "prod@example.com", "password": "password123"})
        # Must fail with 503 because it was forced to call external CMS and did NOT bypass!
        assert resp.status_code == 503
        mock_auth.assert_called_once()

