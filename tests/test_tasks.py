import csv
import io
import re
from contextlib import closing
from datetime import timedelta

import pytest

from productivity_assistant import storage
from productivity_assistant.db import connect


def create(client, **fields):
    response = client.post("/api/tasks", json={"title": "Synthetic task", **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_task_lifecycle_records_history(client, clock):
    task = create(client, title="Draft report", importance=3, due_date="2026-09-30")
    clock.value += timedelta(minutes=5)
    assert client.patch(f"/api/tasks/{task['id']}", json={"due_date": None, "notes": "n"}).json()["due_date"] is None
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}).json()["completed_at"]
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "open"}).json()["completed_at"] is None
    assert client.patch(f"/api/tasks/{task['id']}", json={"notes": "n"}).status_code == 200  # no-op
    history = client.get(f"/api/tasks/{task['id']}/history").json()
    assert [entry["action"] for entry in history] == ["created", "edited", "completed", "reopened"]
    assert history[1]["changes"] == {"due_date": ["2026-09-30", None], "notes": ["", "n"]}
    assert all(entry["actor"] == "you" for entry in history)
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert client.get("/api/tasks", params={"status": "all"}).json() == []


@pytest.mark.parametrize("body", [
    {"title": ""}, {"title": "x" * 201}, {"title": "x", "importance": 4}, {"title": "x", "due_date": "2026-02-30"},
    {"title": "x", "unexpected": 1}, {"title": "x", "effort_minutes": 0}, {"title": "x", "project_id": 99},
])
def test_invalid_tasks_are_rejected(client, body):
    assert client.post("/api/tasks", json=body).status_code in (400, 422)
    assert client.get("/api/tasks").json() == []


def test_required_fields_cannot_be_cleared(client):
    task = create(client)
    assert client.patch(f"/api/tasks/{task['id']}", json={"title": None}).status_code == 400


def test_dependencies_reject_cycles_and_clear_on_delete(client):
    first, second, third = (create(client, title=name)["id"] for name in "ABC")
    assert client.post(f"/api/tasks/{second}/dependencies", json={"blocked_by_id": first}).status_code == 201
    assert client.post(f"/api/tasks/{third}/dependencies", json={"blocked_by_id": second}).status_code == 201
    assert client.post(f"/api/tasks/{first}/dependencies", json={"blocked_by_id": third}).status_code == 400
    assert client.post(f"/api/tasks/{first}/dependencies", json={"blocked_by_id": first}).status_code == 400
    assert client.get(f"/api/tasks/{second}").json()["blocked_by"] == [first]
    assert client.get("/api/tasks").json()[1]["open_blockers"] == 1
    client.delete(f"/api/tasks/{first}")
    assert client.get(f"/api/tasks/{second}").json()["blocked_by"] == []
    assert client.delete(f"/api/tasks/{third}/dependencies/{second}").status_code == 204


def test_projects_filter_tasks(client):
    project = client.post("/api/projects", json={"name": "Client", "private": True}).json()
    assert client.post("/api/projects", json={"name": "client"}).status_code == 400
    create(client, title="In project", project_id=project["id"])
    create(client, title="Elsewhere")
    titles = [task["title"] for task in client.get("/api/tasks", params={"project_id": project["id"]}).json()]
    assert titles == ["In project"]


def test_pages_create_edit_complete_and_delete(client):
    token = client.headers["x-csrf-token"]
    del client.headers["x-csrf-token"]  # browser forms carry the token in the body
    created = client.post("/tasks", data={"csrf_token": token, "title": "Form task", "importance": "3",
                                          "due_date": "", "next": "/"}, follow_redirects=False)
    assert created.status_code == 303 and created.headers["location"] == "/"
    assert "Form task" in client.get("/").text
    task_id = int(re.search(r'href="/tasks/(\d+)"', client.get("/tasks").text).group(1))
    edited = client.post(f"/tasks/{task_id}", data={"csrf_token": token, "title": "Renamed", "notes": "",
                                                    "importance": "1", "due_date": "2026-10-01"})
    assert "Renamed" in edited.text and "2026-10-01" in edited.text
    client.post(f"/tasks/{task_id}/status", data={"csrf_token": token, "status": "done"})
    assert "Renamed" not in client.get("/").text
    assert "completed" in client.get(f"/tasks/{task_id}").text
    client.post(f"/tasks/{task_id}/delete", data={"csrf_token": token})
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_page_errors_are_shown_and_redirects_stay_local(client):
    token = client.headers["x-csrf-token"]
    error = client.post("/tasks", data={"csrf_token": token, "title": "   "})
    assert error.status_code == 400 and 'role="alert"' in error.text
    away = client.post("/tasks", data={"csrf_token": token, "title": "x", "next": "//attacker.example"},
                       follow_redirects=False)
    assert away.headers["location"] == "/tasks"
    assert client.post("/tasks", data={"title": "no token"}, headers={"x-csrf-token": ""}).status_code == 403


def test_user_text_is_escaped(client):
    create(client, title="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in client.get("/").text


def test_exports(client):
    create(client, title="=HYPERLINK(\"http://x\")", notes="Synthetic")
    data = client.get("/api/export").json()
    assert data["format"] == storage.EXPORT_FORMAT
    assert {"tasks", "task_history", "projects", "task_dependencies"} <= set(data["tables"])
    rows = list(csv.DictReader(io.StringIO(client.get("/api/export", params={"format": "csv"}).text)))
    assert rows[0]["title"].startswith("'=")


def test_backup_rotation_verify_and_restore(client, settings, clock):
    create(client, title="Before backup")
    for _ in range(16):
        clock.value += timedelta(seconds=1)
        assert client.post("/api/backups").json()["tasks"] == 1
    backups = storage.list_backups(settings.backup_dir)
    assert len(backups) == 14 and not list(settings.backup_dir.glob("*-wal"))
    create(client, title="After backup")
    clock.value += timedelta(seconds=1)
    safety = storage.restore(backups[0], settings.database, settings.backup_dir, clock.value)
    assert [task["title"] for task in client.get("/api/tasks").json()] == ["Before backup"]
    assert storage.verify_backup(safety)["tasks"] == 2
    corrupt = settings.backup_dir / "assistant-corrupt.sqlite"
    corrupt.write_bytes(b"not a database")
    with pytest.raises(storage.InputError):
        storage.verify_backup(corrupt)
    with closing(connect(settings.database)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
