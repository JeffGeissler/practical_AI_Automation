from contextlib import closing
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from productivity_assistant import briefings, scheduler, storage
from productivity_assistant.db import connect
from productivity_assistant.web import create_app

from .conftest import BASE


def at(day, hour, minute=0):
    return datetime(2026, 9, day, hour, minute, tzinfo=timezone.utc)


def create(client, **fields):
    return client.post("/api/tasks", json=fields).json()["id"]


def run(settings, now):
    with closing(connect(settings.database)) as connection:
        return scheduler.run_due_jobs(connection, settings.backup_dir, now)


def test_schedule_runs_once_per_day_and_catches_up(client, settings):
    assert run(settings, at(28, 7)) == ["backup"]
    assert run(settings, at(28, 8, 5)) == ["morning:schedule"]
    assert run(settings, at(28, 8, 6)) == []
    assert run(settings, at(28, 19)) == ["evening:catch_up"]
    assert run(settings, at(28, 23)) == []
    # App closed overnight, opened mid-afternoon: today's morning briefing, not yesterday's review.
    assert run(settings, at(29, 15)) == ["morning:catch_up", "backup"]
    assert [entry.name[:18] for entry in storage.list_backups(settings.backup_dir)] == [
        "assistant-20260929", "assistant-20260928"]


def test_manual_briefing_does_not_replace_scheduled_run(client, settings, clock):
    clock.value = at(28, 7, 30)
    client.post("/api/briefings", json={"kind": "morning"})
    assert run(settings, at(28, 8)) == ["morning:schedule", "backup"]
    assert client.get("/api/briefings").json()["trigger"] == "schedule"  # newest is shown


def test_morning_and_evening_content(client, clock):
    clock.value = at(27, 10)
    done_yesterday = create(client, title="Sent invoice")
    client.patch(f"/api/tasks/{done_yesterday}", json={"status": "done"})
    clock.value = at(28, 9)
    blocker = create(client, title="Budget review", due_date="2026-09-28")
    waiting = create(client, title="Q3 report", due_date="2026-09-29")
    create(client, title="Pay invoice", due_date="2026-09-26")
    client.post(f"/api/tasks/{waiting}/dependencies", json={"blocked_by_id": blocker})
    morning = client.post("/api/briefings", json={"kind": "morning"}).json()["content"]

    def titles(entries):
        return [entry["title"] for entry in entries]
    assert titles(morning["overdue"]) == ["Pay invoice"]
    assert titles(morning["due_today"]) == ["Budget review"]
    assert titles(morning["top"]) == ["Pay invoice", "Budget review", "Q3 report"]
    assert titles(morning["waiting"]) == ["Q3 report"]
    assert titles(morning["completed_yesterday"]) == ["Sent invoice"]
    assert morning["top"][0]["reasons"] == ["Overdue by 2 days", "Normal importance"]

    clock.value = at(28, 18)
    client.patch(f"/api/tasks/{blocker}", json={"status": "done"})
    evening = client.post("/api/briefings", json={"kind": "evening"}).json()["content"]
    assert titles(evening["completed_today"]) == ["Budget review"]
    assert titles(evening["still_due"]) == ["Pay invoice"]
    assert titles(evening["tomorrow"]) == ["Pay invoice", "Q3 report"]


def test_briefings_are_stored_with_inputs(client, settings):
    create(client, title="Synthetic")
    client.post("/api/briefings", json={"kind": "morning"})
    with closing(connect(settings.database)) as connection:
        stored = briefings.latest(connection, "morning", at(28, 9).date())
    assert stored["content"]["top"][0]["title"] == "Synthetic" and stored["generated_at"].endswith("+00:00")
    assert client.get("/api/briefings", params={"day": "2026-09-01"}).status_code == 404
    assert client.post("/api/briefings", json={"kind": "weekly"}).status_code == 422


def test_startup_catches_up_and_pages_show_briefings(settings, clock):
    clock.value = at(28, 18, 30)
    with TestClient(create_app(settings, clock=clock), base_url=BASE) as client:
        token = client.get("/api/csrf").json()["csrf_token"]
        assert "catch-up" in client.get("/").text
        assert "catch-up" in client.get("/review").text
        assert len(storage.list_backups(settings.backup_dir)) == 1
        assert client.post("/briefings/weekly", data={"csrf_token": token}).status_code == 404
        refreshed = client.post("/briefings/evening", data={"csrf_token": token}, follow_redirects=False)
        assert refreshed.headers["location"] == "/review"


def test_schedule_settings_are_validated(client, settings):
    assert client.put("/api/settings/schedule", json={"morning": "25:00"}).status_code == 422
    assert client.put("/api/settings/schedule", json={"morning": "06:30", "evening": "21:15"}).status_code == 200
    assert run(settings, at(28, 6, 35)) == ["morning:schedule", "backup"]
    assert run(settings, at(28, 21, 30)) == ["evening:catch_up"]
    token = client.headers["x-csrf-token"]
    assert client.post("/settings/schedule", data={"csrf_token": token, "morning": "8am", "evening": "18:00"}
                       ).status_code == 400


def test_scheduler_failure_does_not_stop_the_app(client, monkeypatch):
    def broken(*args):
        raise RuntimeError("disk full")
    monkeypatch.setattr(scheduler, "run_due_jobs", broken)
    assert scheduler.run_once(client.app) == []
    assert client.get("/healthz").status_code == 200


def test_day_boundary_uses_local_time(client, settings):
    local = timezone(timedelta(hours=-7))
    # 23:30 local on the 28th is already the 29th in UTC; the briefing belongs to the 28th.
    assert "morning:catch_up" in run(settings, datetime(2026, 9, 28, 23, 30, tzinfo=local))
    with closing(connect(settings.database)) as connection:
        assert connection.execute("SELECT day FROM briefings").fetchone()[0] == "2026-09-28"
