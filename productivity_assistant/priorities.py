"""Transparent, deterministic priority score. Documented with worked examples in docs/PRIORITIZATION.md."""
import json
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .tasks import InputError, TaskPatch, get_task, stamp, update_task

FACTORS = ("due", "importance", "blocking", "effort", "age")
DEFAULT_WEIGHTS = {factor: 1.0 for factor in FACTORS}
OVERRIDE_POINTS = 20
WAITING_POINTS = -25


class Weights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    due: float = Field(1.0, ge=0, le=3)
    importance: float = Field(1.0, ge=0, le=3)
    blocking: float = Field(1.0, ge=0, le=3)
    effort: float = Field(1.0, ge=0, le=3)
    age: float = Field(1.0, ge=0, le=3)


class OverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["pin", "raise", "lower", "clear"]


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def due_points(days_left):
    if days_left is None:
        return 0, None
    if days_left < 0:
        return 60 + 2 * min(-days_left, 10), f"Overdue by {_plural(-days_left, 'day')}"
    if days_left <= 2:
        return {0: 50, 1: 40, 2: 30}[days_left], ["Due today", "Due tomorrow", "Due in 2 days"][days_left]
    if days_left <= 7:
        return 15, f"Due in {days_left} days"
    if days_left <= 14:
        return 5, f"Due in {days_left} days"
    return 0, None


def effort_points(minutes):
    if minutes is None:
        return 0, None
    if minutes <= 30:
        return 5, f"Quick win ({minutes} min)"
    if minutes <= 60:
        return 2, f"Short ({minutes} min)"
    return 0, None


def get_weights(connection) -> dict:
    row = connection.execute("SELECT value FROM settings WHERE key = 'priority_weights'").fetchone()
    return Weights(**json.loads(row[0])).model_dump() if row else dict(DEFAULT_WEIGHTS)


def set_weights(connection, weights: Weights):
    with connection:
        connection.execute("INSERT INTO settings VALUES ('priority_weights', ?) "
                           "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (weights.model_dump_json(),))


def score_task(task, today: date, weights: dict, blocks: int, waiting_on: list, override) -> dict:
    parts = []

    def add(factor, points, label):
        if points:
            parts.append({"factor": factor, "label": label, "points": round(points * weights.get(factor, 1.0), 1)})

    days_left = (date.fromisoformat(task["due_date"]) - today).days if task["due_date"] else None
    add("due", *due_points(days_left))
    add("importance", {1: 0, 2: 15, 3: 30}[task["importance"]],
        {2: "Normal importance", 3: "High importance"}.get(task["importance"]))
    add("blocking", min(10 * blocks, 30), f"Blocks {_plural(blocks, 'open task')}")
    add("effort", *effort_points(task["effort_minutes"]))
    weeks = (today - datetime.fromisoformat(task["updated_at"]).date()).days // 7
    add("age", min(max(weeks, 0), 10), f"Untouched for {_plural(weeks, 'week')}")
    if waiting_on:
        parts.append({"factor": "waiting", "label": "Waiting on: " + ", ".join(waiting_on),
                      "points": WAITING_POINTS})
    if override in ("raise", "lower"):
        parts.append({"factor": "override", "label": {"raise": "You raised it", "lower": "You lowered it"}[override],
                      "points": OVERRIDE_POINTS if override == "raise" else -OVERRIDE_POINTS})
    return {"score": round(sum(part["points"] for part in parts), 1), "pinned": override == "pin",
            "reasons": parts}


def rank(connection, today: date) -> list:
    """Open, unsnoozed tasks: pinned first (oldest pin first), then score, due date and id."""
    weights = get_weights(connection)
    tasks = connection.execute(
        "SELECT t.*, p.name AS project_name, o.kind AS override, o.created_at AS override_at FROM tasks t "
        "LEFT JOIN projects p ON p.id = t.project_id LEFT JOIN priority_overrides o ON o.task_id = t.id "
        "WHERE t.status = 'open' AND t.deleted_at IS NULL AND (t.snoozed_until IS NULL OR t.snoozed_until <= ?)",
        (today.isoformat(),)).fetchall()
    links = connection.execute(
        "SELECT d.task_id, d.blocked_by_id, b.title AS blocker_title FROM task_dependencies d "
        "JOIN tasks b ON b.id = d.blocked_by_id JOIN tasks t ON t.id = d.task_id "
        "WHERE b.status = 'open' AND b.deleted_at IS NULL AND t.status = 'open' AND t.deleted_at IS NULL").fetchall()
    ranked = []
    for task in tasks:
        blocks = sum(1 for link in links if link["blocked_by_id"] == task["id"])
        waiting = [link["blocker_title"] for link in links if link["task_id"] == task["id"]]
        entry = score_task(task, today, weights, blocks, waiting, task["override"])
        ranked.append(dict(entry, task=dict(task), id=task["id"], title=task["title"]))
    ranked.sort(key=lambda entry: (not entry["pinned"], entry["task"]["override_at"] if entry["pinned"] else "",
                                   -entry["score"], entry["task"]["due_date"] or "9999-12-31", entry["id"]))
    for position, entry in enumerate(ranked, 1):
        entry["rank"] = position
    return ranked


def _feedback(connection, task, kind, today, now):
    current = next((entry for entry in rank(connection, today) if entry["id"] == task["id"]), None)
    connection.execute(
        "INSERT INTO priority_feedback (task_id, kind, at, rank_before, score_before, project_id, importance) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)", (task["id"], kind, stamp(now), current and current["rank"],
                                         current and current["score"], task["project_id"], task["importance"]))


def set_override(connection, task_id: int, kind: str, today: date, now):
    task = get_task(connection, task_id)
    if task["status"] != "open":
        raise InputError("Only open tasks can be reprioritized")
    _feedback(connection, task, kind, today, now)
    with connection:
        if kind == "clear":
            connection.execute("DELETE FROM priority_overrides WHERE task_id = ?", (task_id,))
        else:
            connection.execute("INSERT INTO priority_overrides VALUES (?, ?, ?) ON CONFLICT(task_id) DO UPDATE "
                               "SET kind = excluded.kind, created_at = excluded.created_at",
                               (task_id, kind, stamp(now)))


def snooze(connection, task_id: int, until: date, today: date, now):
    if until <= today:
        raise InputError("Snooze until a future date")
    _feedback(connection, get_task(connection, task_id), "snooze", today, now)
    update_task(connection, task_id, TaskPatch(snoozed_until=until), now)
