"""Factual morning briefing and evening review, built only from stored tasks. No AI."""
import json
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .priorities import rank
from .tasks import stamp

TOP = 5


class BriefingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["morning", "evening"]


def _item(entry) -> dict:
    return {"id": entry["id"], "title": entry["title"], "due_date": entry["task"]["due_date"],
            "score": entry["score"], "reasons": [reason["label"] for reason in entry["reasons"]]}


def _completed_on(connection, day: date, now: datetime) -> list:
    rows = connection.execute("SELECT id, title, completed_at FROM tasks WHERE status = 'done' "
                              "AND deleted_at IS NULL AND completed_at IS NOT NULL ORDER BY completed_at")
    return [{"id": row["id"], "title": row["title"]} for row in rows
            if datetime.fromisoformat(row["completed_at"]).astimezone(now.tzinfo).date() == day]


def morning(connection, now: datetime) -> dict:
    today = now.date()
    ranked = rank(connection, today)

    def due(entry):
        return entry["task"]["due_date"]
    return {
        "overdue": [_item(entry) for entry in ranked if due(entry) and due(entry) < today.isoformat()],
        "due_today": [_item(entry) for entry in ranked if due(entry) == today.isoformat()],
        "top": [_item(entry) for entry in ranked[:TOP]],
        "waiting": [_item(entry) for entry in ranked
                    if any(reason["factor"] == "waiting" for reason in entry["reasons"])],
        "completed_yesterday": _completed_on(connection, today - timedelta(days=1), now),
        "open_count": len(ranked),
    }


def evening(connection, now: datetime) -> dict:
    today = now.date()
    open_now = rank(connection, today)
    return {
        "completed_today": _completed_on(connection, today, now),
        "still_due": [_item(entry) for entry in open_now
                      if entry["task"]["due_date"] and entry["task"]["due_date"] <= today.isoformat()],
        "tomorrow": [_item(entry) for entry in rank(connection, today + timedelta(days=1))[:3]],
        "open_count": len(open_now),
    }


def generate(connection, kind: str, now: datetime, trigger: str = "manual") -> int:
    content = (morning if kind == "morning" else evening)(connection, now)
    with connection:
        return connection.execute(
            "INSERT INTO briefings (kind, day, generated_at, trigger, content) VALUES (?, ?, ?, ?, ?)",
            (kind, now.date().isoformat(), stamp(now), trigger, json.dumps(content))).lastrowid


def latest(connection, kind: str, day: date):
    row = connection.execute("SELECT * FROM briefings WHERE kind = ? AND day = ? ORDER BY id DESC LIMIT 1",
                             (kind, day.isoformat())).fetchone()
    return dict(row, content=json.loads(row["content"])) if row else None
