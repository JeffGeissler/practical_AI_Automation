"""Tasks, projects and dependencies. Every task change writes task_history in the same transaction."""
import json
from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EDITABLE = ("title", "notes", "due_date", "importance", "effort_minutes", "project_id", "status", "snoozed_until")
REQUIRED = ("title", "notes", "importance", "status")


class InputError(ValueError):
    pass


class NotFound(LookupError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskIn(_Strict):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field("", max_length=10000)
    due_date: Optional[date] = None
    importance: int = Field(2, ge=1, le=3)
    effort_minutes: Optional[int] = Field(None, ge=1, le=10080)
    project_id: Optional[int] = None


class TaskPatch(_Strict):
    """Only fields that are sent change; an explicit null clears due date, effort or project."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    notes: Optional[str] = Field(None, max_length=10000)
    due_date: Optional[date] = None
    importance: Optional[int] = Field(None, ge=1, le=3)
    effort_minutes: Optional[int] = Field(None, ge=1, le=10080)
    project_id: Optional[int] = None
    status: Optional[Literal["open", "done"]] = None
    snoozed_until: Optional[date] = None


class ProjectIn(_Strict):
    name: str = Field(min_length=1, max_length=100)
    private: bool = False


def stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat(timespec="seconds")


def _stored(value):
    return value.isoformat() if isinstance(value, date) else value


def _check_project(connection, project_id):
    if project_id is not None and not connection.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise InputError("Unknown project")


def record(connection, task_id, now, action, changes=None, actor="you"):
    connection.execute("INSERT INTO task_history (task_id, at, actor, action, changes) VALUES (?, ?, ?, ?, ?)",
                       (task_id, stamp(now), actor, action, json.dumps(changes or {}, sort_keys=True)))


def create_task(connection, data: TaskIn, now, actor="you", source="manual") -> int:
    _check_project(connection, data.project_id)
    values = {key: _stored(value) for key, value in data.model_dump().items()}
    with connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, notes, due_date, importance, effort_minutes, project_id, source, "
            "created_at, updated_at) VALUES (:title, :notes, :due_date, :importance, :effort_minutes, "
            ":project_id, :source, :at, :at)", dict(values, source=source, at=stamp(now)))
        record(connection, cursor.lastrowid, now, "created",
               {key: [None, value] for key, value in values.items() if value not in (None, "")}, actor)
    return cursor.lastrowid


def get_task(connection, task_id: int):
    row = connection.execute(
        "SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
        "WHERE t.id = ? AND t.deleted_at IS NULL", (task_id,)).fetchone()
    if row is None:
        raise NotFound(f"Task {task_id} not found")
    return row


def list_tasks(connection, status: Optional[str] = "open", project_id: Optional[int] = None):
    query = ("SELECT t.*, p.name AS project_name, (SELECT count(*) FROM task_dependencies d "
             "JOIN tasks b ON b.id = d.blocked_by_id WHERE d.task_id = t.id AND b.status = 'open' "
             "AND b.deleted_at IS NULL) AS open_blockers FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
             "WHERE t.deleted_at IS NULL")
    parameters = []
    if status:
        query += " AND t.status = ?"
        parameters.append(status)
    if project_id is not None:
        query += " AND t.project_id = ?"
        parameters.append(project_id)
    query += " ORDER BY t.status, t.due_date IS NULL, t.due_date, t.importance DESC, t.id"
    return connection.execute(query, parameters).fetchall()


def update_task(connection, task_id: int, patch: TaskPatch, now, actor="you") -> dict:
    current = get_task(connection, task_id)
    sent = patch.model_fields_set
    for field in REQUIRED:
        if field in sent and getattr(patch, field) is None:
            raise InputError(f"{field} cannot be empty")
    if "project_id" in sent:
        _check_project(connection, patch.project_id)
    changes = {}
    for field in EDITABLE:
        if field in sent and _stored(getattr(patch, field)) != current[field]:
            changes[field] = [current[field], _stored(getattr(patch, field))]
    if not changes:
        return {}
    assignments = {field: new for field, (_, new) in changes.items()}
    if "status" in changes:
        assignments["completed_at"] = stamp(now) if assignments["status"] == "done" else None
    assignments["updated_at"] = stamp(now)
    action = "edited"
    if list(changes) == ["status"]:
        action = "completed" if assignments["status"] == "done" else "reopened"
    with connection:
        connection.execute(f"UPDATE tasks SET {', '.join(f'{key} = :{key}' for key in assignments)} "
                           "WHERE id = :id", dict(assignments, id=task_id))
        record(connection, task_id, now, action, changes, actor)
    return changes


def delete_task(connection, task_id: int, now, actor="you"):
    get_task(connection, task_id)
    links = [dict(row) for row in connection.execute(
        "SELECT task_id, blocked_by_id FROM task_dependencies WHERE task_id = ? OR blocked_by_id = ?",
        (task_id, task_id))]
    with connection:
        connection.execute("UPDATE tasks SET deleted_at = ?, updated_at = ? WHERE id = ?",
                           (stamp(now), stamp(now), task_id))
        connection.execute("DELETE FROM task_dependencies WHERE task_id = ? OR blocked_by_id = ?",
                           (task_id, task_id))
        record(connection, task_id, now, "deleted", {"removed_dependencies": links} if links else {}, actor)


def add_dependency(connection, task_id: int, blocked_by_id: int, now, actor="you"):
    get_task(connection, task_id)
    get_task(connection, blocked_by_id)
    if task_id == blocked_by_id:
        raise InputError("A task cannot wait on itself")
    seen, pending = set(), [blocked_by_id]
    while pending:
        current = pending.pop()
        if current == task_id:
            raise InputError("That would create a circular dependency")
        if current not in seen:
            seen.add(current)
            pending.extend(row[0] for row in connection.execute(
                "SELECT blocked_by_id FROM task_dependencies WHERE task_id = ?", (current,)))
    with connection:
        added = connection.execute("INSERT OR IGNORE INTO task_dependencies VALUES (?, ?)",
                                   (task_id, blocked_by_id)).rowcount
        if added:
            record(connection, task_id, now, "dependency added", {"blocked_by": [None, blocked_by_id]}, actor)


def remove_dependency(connection, task_id: int, blocked_by_id: int, now, actor="you"):
    with connection:
        removed = connection.execute("DELETE FROM task_dependencies WHERE task_id = ? AND blocked_by_id = ?",
                                     (task_id, blocked_by_id)).rowcount
        if not removed:
            raise NotFound("Dependency not found")
        record(connection, task_id, now, "dependency removed", {"blocked_by": [blocked_by_id, None]}, actor)


def dependencies(connection, task_id: int) -> dict:
    def tasks(query):
        return connection.execute(query + " AND t.deleted_at IS NULL ORDER BY t.id", (task_id,)).fetchall()
    return {
        "blocked_by": tasks("SELECT t.id, t.title, t.status FROM task_dependencies d "
                            "JOIN tasks t ON t.id = d.blocked_by_id WHERE d.task_id = ?"),
        "blocks": tasks("SELECT t.id, t.title, t.status FROM task_dependencies d "
                        "JOIN tasks t ON t.id = d.task_id WHERE d.blocked_by_id = ?"),
    }


def dependencies_ids(connection, task_id: int) -> dict:
    return {key: [row["id"] for row in rows] for key, rows in dependencies(connection, task_id).items()}


def history(connection, task_id: int):
    return [dict(row, changes=json.loads(row["changes"])) for row in connection.execute(
        "SELECT at, actor, action, changes FROM task_history WHERE task_id = ? ORDER BY id", (task_id,))]


def create_project(connection, data: ProjectIn, now) -> int:
    try:
        with connection:
            return connection.execute("INSERT INTO projects (name, private, created_at) VALUES (?, ?, ?)",
                                      (data.name, int(data.private), stamp(now))).lastrowid
    except Exception as error:
        if "UNIQUE" in str(error):
            raise InputError("A project with that name already exists") from None
        raise


def list_projects(connection):
    return connection.execute(
        "SELECT p.*, (SELECT count(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'open' "
        "AND t.deleted_at IS NULL) AS open_tasks FROM projects p ORDER BY p.name").fetchall()
