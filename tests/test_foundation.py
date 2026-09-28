import os
import stat
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from productivity_assistant.config import REPOSITORY, load_settings
from productivity_assistant.db import connect, migrate
from productivity_assistant.web import create_app

from .conftest import BASE

WEIGHTS = "/api/settings/priority-weights"


def test_starts_and_serves_today(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200 and "Today" in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_data_folder_must_be_outside_repository(tmp_path):
    with pytest.raises(ValueError):
        load_settings({"PA_DATA_DIR": str(REPOSITORY / "private")})
    assert load_settings({"PA_DATA_DIR": str(tmp_path)}).database == tmp_path.resolve() / "assistant.sqlite"


def test_private_files_are_owner_only(client, settings):
    assert stat.S_IMODE(os.stat(settings.data_dir).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(settings.data_dir / "session.key").st_mode) == 0o600


def test_migrations_are_versioned_and_idempotent(settings, client):
    with closing(connect(settings.database)) as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
        assert versions[0] == 1 and versions == list(range(1, len(versions) + 1))
        assert migrate(connection) == []


def test_session_cookie_is_strict(settings, clock):
    with TestClient(create_app(settings, clock=clock), base_url=BASE) as fresh:
        cookie = fresh.get("/").headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_unknown_host_is_rejected(client):
    """DNS rebinding: an attacker's name resolving to 127.0.0.1 arrives with its own Host."""
    assert client.get("/", headers={"host": "attacker.example:8000"}).status_code == 400
    assert client.get("/", headers={"host": "127.0.0.1:9999"}).status_code == 400


@pytest.mark.parametrize("headers", [
    {"origin": "https://attacker.example"},
    {"origin": "null"},
    {"referer": "https://attacker.example/page"},
    {"sec-fetch-site": "cross-site"},
    {"sec-fetch-site": "same-site"},
])
def test_cross_site_change_is_rejected(client, headers):
    response = client.put(WEIGHTS, json={"due": 2}, headers=headers)
    assert response.status_code == 403


def test_change_requires_csrf_token(client):
    del client.headers["x-csrf-token"]
    assert client.put(WEIGHTS, json={"due": 2}).status_code == 403
    assert client.put(WEIGHTS, json={"due": 2},
                      headers={"x-csrf-token": "0" * 64}).status_code == 403


def test_csrf_token_is_bound_to_session(client, settings, clock):
    with TestClient(create_app(settings, clock=clock), base_url=BASE) as other:
        other.get("/")
        stolen = client.headers["x-csrf-token"]
        assert other.put(WEIGHTS, json={"due": 2},
                         headers={"x-csrf-token": stolen}).status_code == 403


def test_same_origin_change_succeeds(client):
    response = client.put(WEIGHTS, json={"due": 2}, headers={"origin": BASE})
    assert response.status_code == 200
