from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from productivity_assistant.db import connect
from productivity_assistant.priorities import due_points


def create(client, **fields):
    response = client.post("/api/tasks", json=fields)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def scores(client):
    return [(entry["title"], entry["score"], entry["pinned"]) for entry in client.get("/api/priorities").json()]


@pytest.fixture
def example(client, clock):
    """The worked example in docs/PRIORITIZATION.md."""
    clock.value = datetime(2026, 8, 24, 9, tzinfo=timezone.utc)
    ids = {"notes": create(client, title="Tidy notes", importance=1)}
    clock.value = datetime(2026, 9, 28, 9, tzinfo=timezone.utc)
    ids["invoice"] = create(client, title="Pay invoice", due_date="2026-09-27", effort_minutes=15)
    ids["budget"] = create(client, title="Budget review", due_date="2026-10-02", importance=3)
    ids["report"] = create(client, title="Q3 report", due_date="2026-09-29", importance=3)
    ids["dentist"] = create(client, title="Call dentist")
    client.post(f"/api/tasks/{ids['report']}/dependencies", json={"blocked_by_id": ids["budget"]})
    client.post(f"/api/priorities/{ids['dentist']}/override", json={"kind": "pin"})
    return ids


def test_documented_example(client, example):
    assert scores(client) == [("Call dentist", 15, True), ("Pay invoice", 82, False),
                              ("Budget review", 55, False), ("Q3 report", 45, False), ("Tidy notes", 5, False)]
    reasons = {entry["title"]: [reason["label"] for reason in entry["reasons"]]
               for entry in client.get("/api/priorities").json()}
    assert reasons["Q3 report"] == ["Due tomorrow", "High importance", "Waiting on: Budget review"]
    assert reasons["Budget review"][-1] == "Blocks 1 open task"
    assert reasons["Tidy notes"] == ["Untouched for 5 weeks"]
    client.patch(f"/api/tasks/{example['budget']}", json={"status": "done"})
    assert ("Q3 report", 70, False) in scores(client)


def test_overrides_persist_and_are_recorded(client, example, settings):
    client.post(f"/api/priorities/{example['notes']}/override", json={"kind": "raise"})
    client.post(f"/api/priorities/{example['invoice']}/override", json={"kind": "lower"})
    ranked = scores(client)
    assert ("Tidy notes", 25, False) in ranked and ("Pay invoice", 62, False) in ranked
    client.post(f"/api/priorities/{example['dentist']}/override", json={"kind": "clear"})
    assert scores(client)[0] == ("Pay invoice", 62, False)
    assert client.post(f"/api/priorities/{example['notes']}/override", json={"kind": "boost"}).status_code == 422
    with closing(connect(settings.database)) as connection:
        feedback = connection.execute("SELECT kind, rank_before FROM priority_feedback ORDER BY id").fetchall()
    assert [tuple(row) for row in feedback] == [("pin", 4), ("raise", 5), ("lower", 2), ("clear", 1)]


def test_weights_change_scores_and_reset(client, example):
    assert client.put("/api/settings/priority-weights", json={"due": 0, "importance": 2}).status_code == 200
    assert ("Pay invoice", 35, False) in scores(client)  # 0 due + 30 importance + 5 effort
    assert client.put("/api/settings/priority-weights", json={"due": 5}).status_code == 422
    assert client.put("/api/settings/priority-weights", json={}).status_code == 200
    assert ("Pay invoice", 82, False) in scores(client)


def test_snooze_hides_until_date(client, example, clock):
    assert client.post(f"/api/tasks/{example['invoice']}/snooze", json={"until": "2026-09-28"}).status_code == 400
    assert client.post(f"/api/tasks/{example['invoice']}/snooze", json={"until": "2026-09-30"}).status_code == 200
    assert "Pay invoice" not in [title for title, _, _ in scores(client)]
    clock.value += timedelta(days=2)
    assert "Pay invoice" in [title for title, _, _ in scores(client)]


@pytest.mark.parametrize("days_left, points", [
    (-30, 80), (-1, 62), (0, 50), (1, 40), (2, 30), (3, 15), (7, 15), (8, 5), (14, 5), (15, 0), (None, 0)])
def test_due_points(days_left, points):
    assert due_points(days_left)[0] == points


def test_today_page_shows_reasons_and_buttons(client, example):
    token = client.headers["x-csrf-token"]
    page = client.get("/").text
    assert "Overdue by 1 day (+62)" in page and "Waiting on: Budget review (-25)" in page
    assert page.index("Call dentist") < page.index("Pay invoice") < page.index("Tidy notes")
    client.post(f"/priorities/{example['notes']}", data={"csrf_token": token, "kind": "raise"})
    assert "You raised it (+20)" in client.get("/").text
    client.post(f"/tasks/{example['invoice']}/snooze", data={"csrf_token": token})
    assert "Pay invoice" not in client.get("/").text
    reset = client.post("/settings/weights", data={"csrf_token": token, "reset": "1"}, follow_redirects=False)
    assert reset.status_code == 303
    assert client.post("/settings/weights", data={"csrf_token": token, "due": "9", "importance": "1",
                                                  "blocking": "1", "effort": "1", "age": "1"}).status_code == 400
