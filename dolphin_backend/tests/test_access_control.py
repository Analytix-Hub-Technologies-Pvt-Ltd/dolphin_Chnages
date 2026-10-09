"""Authorization regressions; use a fake database, never production data."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.access_control import create_access_token
from api.dependencies import get_db_pool
from api.session_router import router as sessions_router
from api.user_router import router as users_router
from api.login_router import router as login_router
from config import settings
from services.session_service import SessionService


class Pool:
    _closed = False

    def __init__(self):
        self.user = {"id": "owner", "email": "regular@example.com", "role_name": "USER"}
        self.fetchrow = AsyncMock(side_effect=self.lookup)
        self.fetchval = AsyncMock(return_value=0)
        self.fetch = AsyncMock(return_value=[])

    async def lookup(self, query, *args):
        if "SELECT u.id, u.email, ur.role_name FROM users" in query:
            return self.user
        return None

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "access_token_secret", "test-secret-" * 6)
    pool = Pool()
    app = FastAPI()
    app.include_router(sessions_router)
    app.include_router(users_router)
    app.include_router(login_router)
    app.dependency_overrides[get_db_pool] = lambda: pool
    with TestClient(app) as http:
        yield http, pool


def headers():
    return {"Authorization": "Bearer " + create_access_token("owner")}


@pytest.mark.parametrize("path", ["/users", "/sessions", "/sessions/", "/sessions/s1",
                                  "/sessions/get_all/sessions/", "/sessions/saved/owner"])
def test_missing_token_denied(client, path):
    http, pool = client
    assert http.get(path).status_code == 401
    pool.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("path", ["/users?admin_user_id=admin", "/sessions/?all_users=true",
                                  "/sessions/?user_id=other", "/sessions?user_id=other",
                                  "/sessions/s1?user_id=other", "/sessions/get_all/sessions/",
                                  "/sessions/saved/other"])
def test_regular_user_cannot_escalate(client, path):
    http, pool = client
    assert http.get(path, headers=headers()).status_code == 403
    pool.fetch.assert_not_awaited()


def test_role_change_requires_super_admin(client):
    http, pool = client
    assert http.put("/users/target/role", json={"role_id": 2}, headers=headers()).status_code == 403
    assert all("UPDATE" not in call.args[0] for call in pool.fetchrow.await_args_list)


def test_own_paginated_sessions_filter_both_count_and_data(client):
    http, pool = client
    response = http.get("/sessions/?limit=7&offset=2&student_name=Ann&session_date=2026-01-01", headers=headers())
    assert response.status_code == 200
    count = pool.fetchval.await_args
    data = pool.fetch.await_args
    assert "cs.user_id = $1" in count.args[0]
    assert "cs.user_id = $1" in data.args[0]
    assert count.args[1:] == ("owner", date(2026, 1, 1), date(2026, 1, 2), "%Ann%")
    assert data.args[1:] == (*count.args[1:], 7, 2)
    assert "LIMIT $5" in data.args[0]


def test_privileged_all_sessions_and_users(client):
    http, pool = client
    pool.user["role_name"] = "SUPER_ADMIN"
    assert http.get("/sessions/?all_users=true", headers=headers()).status_code == 200
    assert "AND cs.user_id =" not in pool.fetch.await_args.args[0]
    assert http.get("/users", headers=headers()).status_code == 200
    assert http.get("/users?admin_user_id=someone_else", headers=headers()).status_code == 403


@pytest.mark.parametrize("role", ["ADMIN", "SUPER_ADMIN"])
def test_privileged_defaults_to_all_sessions(client, role):
    http, pool = client
    pool.user["role_name"] = role
    assert http.get("/sessions/?limit=10&offset=10", headers=headers()).status_code == 200
    assert "AND cs.user_id =" not in pool.fetch.await_args.args[0]
    assert "AND cs.user_id =" not in pool.fetchval.await_args.args[0]
    assert pool.fetch.await_args.args[1:] == (10, 10)


@pytest.mark.parametrize("role", ["ADMIN", "SUPER_ADMIN"])
@pytest.mark.parametrize("query,owner", [("all_users=false", "owner"), ("user_id=other", "other"), ("user_id=owner", "owner")])
def test_privileged_can_explicitly_filter_owner(client, role, query, owner):
    http, pool = client
    pool.user["role_name"] = role
    assert http.get("/sessions/?" + query, headers=headers()).status_code == 200
    assert "AND cs.user_id =" in pool.fetch.await_args.args[0]
    assert pool.fetch.await_args.args[1] == owner
    assert pool.fetchval.await_args.args[1] == owner


@pytest.mark.parametrize("role", [None, "UNKNOWN", "USER"])
def test_non_admin_default_stays_personal(client, role):
    http, pool = client
    pool.user["role_name"] = role
    assert http.get("/sessions/", headers=headers()).status_code == 200
    assert pool.fetch.await_args.args[1] == "owner"
    assert pool.fetchval.await_args.args[1] == "owner"


def test_detail_mismatch_has_no_unscoped_fallback(client):
    http, pool = client
    assert http.get("/sessions/s1", headers=headers()).status_code == 404
    calls = [call for call in pool.fetchrow.await_args_list if "chat_sessions" in call.args[0]]
    assert len(calls) == 1
    assert calls[0].args[1:] == ("s1", "owner")


def test_privileged_can_lookup_any_session(client):
    http, pool = client
    pool.user["role_name"] = "SUPER_ADMIN"
    assert http.get("/sessions/s1", headers=headers()).status_code == 404
    assert pool.fetchrow.await_args.args[1:] == ("s1",)


@pytest.mark.parametrize("kind", ["expired", "forged", "wrong_audience"])
def test_invalid_tokens_denied_before_database(client, kind):
    http, pool = client
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "owner", "iat": now, "iss": "dolphin-api",
                        "aud": "other" if kind == "wrong_audience" else "dolphin-api",
                        "exp": now + timedelta(hours=-1 if kind == "expired" else 1)},
                       "wrong-secret" if kind == "forged" else settings.access_token_secret,
                       algorithm="HS256")
    assert http.get("/users", headers={"Authorization": "Bearer " + token}).status_code == 401
    pool.fetchrow.assert_not_awaited()


def test_ownership_service_does_not_retry_without_owner():
    pool = Pool()
    assert asyncio.run(SessionService(pool).get_session("s1", "wrong-owner")) is None
    assert pool.fetchrow.await_count == 1


def test_privileged_role_change_reaches_update(client):
    http, pool = client
    pool.user["role_name"] = "SUPER_ADMIN"
    # Missing target yields 404 after the authorized update attempt.
    assert http.put("/users/target/role", json={"role_id": 2}, headers=headers()).status_code == 404
    assert "UPDATE users" in pool.fetchrow.await_args.args[0]
    assert pool.fetchrow.await_args.args[1:] == ("target", 2)


@pytest.mark.parametrize("query", ["user_id=", "all_users=true&user_id=owner"])
def test_ambiguous_or_empty_scope_rejected(client, query):
    http, pool = client
    pool.user["role_name"] = "SUPER_ADMIN"
    assert http.get("/sessions/?" + query, headers=headers()).status_code == 400
    pool.fetch.assert_not_awaited()


@pytest.mark.parametrize("privileged", [False, True])
def test_authorized_session_details_return_messages(client, privileged):
    http, pool = client
    if privileged:
        pool.user["role_name"] = "SUPER_ADMIN"
    now = datetime.now(timezone.utc)
    async def lookup(query, *args):
        if "SELECT u.id, u.email, ur.role_name FROM users" in query:
            return pool.user
        return {"session_id": "s1", "title": "Session", "created_at": now,
                "updated_at": now, "messages": [{"role": "user", "content": "Hello"}]}
    pool.fetchrow.side_effect = lookup
    response = http.get("/sessions/s1", headers=headers())
    assert response.status_code == 200
    assert response.json()["messages"][0]["content"] == "Hello"
    expected = ("s1",) if privileged else ("s1", "owner")
    assert pool.fetchrow.await_args.args[1:] == expected


def test_database_role_change_revokes_privilege_immediately(client):
    http, pool = client
    token_headers = headers()
    pool.user["role_name"] = "SUPER_ADMIN"
    assert http.get("/users", headers=token_headers).status_code == 200
    pool.user["role_name"] = "USER"
    assert http.get("/users", headers=token_headers).status_code == 403


def test_deleted_user_denied(client):
    http, pool = client
    pool.user = None
    assert http.get("/sessions/", headers=headers()).status_code == 401


def test_unconfigured_signing_key_fails_closed(client, monkeypatch):
    http, pool = client
    token_headers = headers()
    monkeypatch.setattr(settings, "access_token_secret", "")
    assert http.get("/users", headers=token_headers).status_code == 503
    pool.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("role", ["ADMIN", "SUPER_ADMIN"])
@pytest.mark.parametrize("path", ["/sessions/?all_users=true", "/sessions/?user_id=other",
                                  "/sessions?user_id=other", "/sessions/saved/other",
                                  "/sessions/get_all/sessions/"])
def test_administrative_session_reads(client, role, path):
    http, pool = client
    pool.user["role_name"] = role
    assert http.get(path, headers=headers()).status_code == 200


@pytest.mark.parametrize("role", ["USER", "ADMIN", None, "UNKNOWN"])
def test_only_super_admin_can_manage_users(client, role):
    http, pool = client
    pool.user["role_name"] = role
    assert http.get("/users", headers=headers()).status_code == 403
    assert http.put("/users/target/role", json={"role_id": 3}, headers=headers()).status_code == 403
    assert http.post("/login/create", json={"name": "New", "role_id": 3}, headers=headers()).status_code == 403


@pytest.mark.parametrize("role", [None, "UNKNOWN", "USER"])
def test_missing_or_non_admin_role_cannot_read_other_sessions(client, role):
    http, pool = client
    pool.user["role_name"] = role
    assert http.get("/sessions/?all_users=true", headers=headers()).status_code == 403
    assert http.get("/sessions/s1?user_id=other", headers=headers()).status_code == 403


def test_admin_details_and_demotion(client):
    http, pool = client
    pool.user["role_name"] = "ADMIN"
    token_headers = headers()
    assert http.get("/sessions/s1", headers=token_headers).status_code == 404
    assert pool.fetchrow.await_args.args[1:] == ("s1",)
    pool.user["role_name"] = "USER"
    assert http.get("/sessions/s1", headers=token_headers).status_code == 404
    assert pool.fetchrow.await_args.args[1:] == ("s1", "owner")


def test_unauthenticated_role_assignment_denied(client):
    http, pool = client
    assert http.post("/login/create", json={"name": "New", "role_id": 3}).status_code == 401
    pool.fetchrow.assert_not_awaited()


def test_paginated_sessions_include_stored_chat_count(client):
    http, pool = client
    pool.fetchval.return_value = 1
    pool.fetch.return_value = [{"id": "owner", "username": "Example", "chat_title": "Test", "time": None, "session_id": "s1", "chat_count": 3}]
    response = http.get("/sessions/", headers=headers())
    assert response.status_code == 200
    assert response.json()["data"][0]["chat_count"] == 3
    query = pool.fetch.await_args.args[0]
    assert "metadata->'chat_count'" in query
    assert "messages" not in query


def test_unprocessed_session_count_is_null(client):
    http, pool = client
    pool.fetchval.return_value = 1
    pool.fetch.return_value = [{"id": "owner", "username": "Example", "chat_title": "Test", "time": None, "session_id": "s1", "chat_count": None}]
    response = http.get("/sessions/", headers=headers())
    assert response.status_code == 200
    assert response.json()["data"][0]["chat_count"] is None
