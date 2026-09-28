"""JSON API. Pydantic validates requests; services own every change."""
import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from . import storage, tasks
from .security import csrf_token
from .web import get_db, now

router = APIRouter()


class DependencyIn(BaseModel):
    blocked_by_id: int


@router.get("/csrf")
def csrf(request: Request):
    """Token for API clients on this Mac; other sites cannot read it (no CORS)."""
    return {"csrf_token": csrf_token(request)}


@router.put("/settings/{key}")
def put_setting(key: str, body: dict, connection=Depends(get_db)):
    value = str(body.get("value", ""))
    with connection:
        connection.execute("INSERT INTO settings VALUES (?, ?) "
                           "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    return {"key": key, "value": value}


def task_json(connection, task_id):
    return dict(tasks.get_task(connection, task_id), **tasks.dependencies_ids(connection, task_id))


@router.get("/tasks")
def list_tasks(status: Optional[Literal["open", "done", "all"]] = "open", project_id: Optional[int] = None,
               connection=Depends(get_db)):
    return [dict(row) for row in tasks.list_tasks(connection, None if status == "all" else status, project_id)]


@router.post("/tasks", status_code=201)
def create_task(body: tasks.TaskIn, request: Request, connection=Depends(get_db)):
    return task_json(connection, tasks.create_task(connection, body, now(request)))


@router.get("/tasks/{task_id}")
def get_task(task_id: int, connection=Depends(get_db)):
    return task_json(connection, task_id)


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, body: tasks.TaskPatch, request: Request, connection=Depends(get_db)):
    tasks.update_task(connection, task_id, body, now(request))
    return task_json(connection, task_id)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, request: Request, connection=Depends(get_db)):
    tasks.delete_task(connection, task_id, now(request))
    return Response(status_code=204)


@router.get("/tasks/{task_id}/history")
def task_history(task_id: int, connection=Depends(get_db)):
    tasks.get_task(connection, task_id)
    return tasks.history(connection, task_id)


@router.post("/tasks/{task_id}/dependencies", status_code=201)
def add_dependency(task_id: int, body: DependencyIn, request: Request, connection=Depends(get_db)):
    tasks.add_dependency(connection, task_id, body.blocked_by_id, now(request))
    return task_json(connection, task_id)


@router.delete("/tasks/{task_id}/dependencies/{blocked_by_id}", status_code=204)
def remove_dependency(task_id: int, blocked_by_id: int, request: Request, connection=Depends(get_db)):
    tasks.remove_dependency(connection, task_id, blocked_by_id, now(request))
    return Response(status_code=204)


@router.get("/projects")
def list_projects(connection=Depends(get_db)):
    return [dict(row) for row in tasks.list_projects(connection)]


@router.post("/projects", status_code=201)
def create_project(body: tasks.ProjectIn, request: Request, connection=Depends(get_db)):
    project_id = tasks.create_project(connection, body, now(request))
    return dict(connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


@router.get("/export")
def export(request: Request, format: Literal["json", "csv"] = "json", connection=Depends(get_db)):
    moment = now(request)
    name = f"assistant-export-{moment.strftime('%Y%m%d-%H%M%S')}"
    if format == "csv":
        return Response(storage.export_tasks_csv(connection), media_type="text/csv",
                        headers={"content-disposition": f'attachment; filename="{name}-tasks.csv"'})
    return Response(json.dumps(storage.export_data(connection, moment), indent=1),
                    media_type="application/json",
                    headers={"content-disposition": f'attachment; filename="{name}.json"'})


@router.post("/backups", status_code=201)
def make_backup(request: Request, connection=Depends(get_db)):
    path = storage.backup(connection, request.app.state.settings.backup_dir, now(request))
    return storage.verify_backup(path)
