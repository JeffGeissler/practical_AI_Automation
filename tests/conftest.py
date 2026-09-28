from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from productivity_assistant.config import Settings
from productivity_assistant.web import create_app

BASE = "http://127.0.0.1:8000"


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def client(settings, clock):
    with TestClient(create_app(settings, clock=clock), base_url=BASE) as test_client:
        test_client.headers["x-csrf-token"] = test_client.get("/api/csrf").json()["csrf_token"]
        yield test_client
