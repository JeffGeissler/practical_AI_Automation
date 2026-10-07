"""Server-rendered pages. Every change is a POST form followed by a redirect."""
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from datetime import timedelta

from . import ai, briefings, capture, priorities, scheduler, storage, tasks
from .web import describe, get_db, now, render, today

router = APIRouter()
FAILURES = (ValidationError, tasks.InputError)


def safe_next(value, default: str) -> str:
    """Only same-site paths, so a crafted form cannot redirect elsewhere."""
    if isinstance(value, str) and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return default


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def task_fields(form) -> dict:
    data = {"title": form.get("title", ""), "notes": form.get("notes", "")}
    for key in ("due_date", "importance", "effort_minutes", "project_id"):
        data[key] = (form.get(key) or "").strip() or None
    if data["importance"] is None:
        del data["importance"]
    return data


@router.get("/")
def today_page(request: Request, connection=Depends(get_db)):
    return render(request, "today.html", ranked=priorities.rank(connection, today(request)),
                  briefing=briefings.latest(connection, "morning", today(request)))


@router.get("/review")
def review_page(request: Request, connection=Depends(get_db)):
    return render(request, "review.html", briefing=briefings.latest(connection, "evening", today(request)))


@router.post("/briefings/{kind}")
def make_briefing(kind: str, request: Request, connection=Depends(get_db)):
    if kind not in ("morning", "evening"):
        raise tasks.NotFound("Unknown briefing")
    briefings.generate(connection, kind, now(request))
    return redirect("/" if kind == "morning" else "/review")


@router.post("/priorities/{task_id}")
async def override(task_id: int, request: Request, connection=Depends(get_db)):
    form = await request.form()
    try:
        kind = priorities.OverrideIn(kind=form.get("kind")).kind
        priorities.set_override(connection, task_id, kind, today(request), now(request))
    except FAILURES as error:
        return render(request, "today.html", 400, error=describe(error),
                      ranked=priorities.rank(connection, today(request)),
                      briefing=briefings.latest(connection, "morning", today(request)))
    return redirect("/")


@router.post("/tasks/{task_id}/snooze")
def snooze(task_id: int, request: Request, connection=Depends(get_db)):
    priorities.snooze(connection, task_id, today(request) + timedelta(days=1), today(request), now(request))
    return redirect("/")


def tasks_context(connection, status="open", project_id=None):
    return {"tasks": tasks.list_tasks(connection, None if status == "all" else status, project_id),
            "projects": tasks.list_projects(connection), "status": status, "project_id": project_id}


@router.get("/tasks")
def task_list(request: Request, status: str = "open", project_id: Optional[int] = None,
              connection=Depends(get_db)):
    if status not in ("open", "done", "all"):
        status = "open"
    return render(request, "tasks.html", **tasks_context(connection, status, project_id))


@router.post("/tasks")
async def create_task(request: Request, connection=Depends(get_db)):
    form = await request.form()
    call_id = form.get("ai_call_id", "")
    try:
        data = tasks.TaskIn(**task_fields(form))
        actor = "ai_accepted" if call_id.isdigit() and ai.mark_accepted(connection, int(call_id)) else "you"
        tasks.create_task(connection, data, now(request), actor=actor,
                          source="capture" if actor == "ai_accepted" else "manual")
    except FAILURES as error:
        return render(request, "tasks.html", 400, error=describe(error), **tasks_context(connection))
    return redirect(safe_next(form.get("next"), "/tasks"))


@router.post("/capture")
async def capture_note(request: Request, connection=Depends(get_db)):
    """Show the note as an editable draft; saving happens only through POST /tasks."""
    form = await request.form()
    try:
        note = capture.CaptureIn(text=form.get("text", ""))
    except ValidationError as error:
        return render(request, "today.html", 400, error=describe(error),
                      ranked=priorities.rank(connection, today(request)),
                      briefing=briefings.latest(connection, "morning", today(request)))
    result = capture.draft(connection, note.text, now(request), request.app.state.gateway)
    return render(request, "capture.html", draft=result, projects=tasks.list_projects(connection))


def task_context(connection, task_id):
    task = tasks.get_task(connection, task_id)
    candidates = [row for row in tasks.list_tasks(connection) if row["id"] != task_id]
    return {"task": task, "links": tasks.dependencies(connection, task_id), "candidates": candidates,
            "history": tasks.history(connection, task_id), "projects": tasks.list_projects(connection)}


@router.get("/tasks/{task_id}")
def task_detail(task_id: int, request: Request, connection=Depends(get_db)):
    return render(request, "task.html", **task_context(connection, task_id))


async def _task_change(request, connection, task_id, change):
    form = await request.form()
    try:
        change(form)
    except FAILURES as error:
        return render(request, "task.html", 400, error=describe(error), **task_context(connection, task_id))
    return redirect(safe_next(form.get("next"), f"/tasks/{task_id}"))


@router.post("/tasks/{task_id}")
async def edit_task(task_id: int, request: Request, connection=Depends(get_db)):
    return await _task_change(request, connection, task_id, lambda form: tasks.update_task(
        connection, task_id, tasks.TaskPatch(**task_fields(form)), now(request)))


@router.post("/tasks/{task_id}/status")
async def set_status(task_id: int, request: Request, connection=Depends(get_db)):
    return await _task_change(request, connection, task_id, lambda form: tasks.update_task(
        connection, task_id, tasks.TaskPatch(status=form.get("status")), now(request)))


@router.post("/tasks/{task_id}/delete")
async def delete_task(task_id: int, request: Request, connection=Depends(get_db)):
    tasks.delete_task(connection, task_id, now(request))
    return redirect("/tasks")


@router.post("/tasks/{task_id}/dependencies")
async def add_dependency(task_id: int, request: Request, connection=Depends(get_db)):
    def change(form):
        blocker = form.get("blocked_by_id", "")
        if not blocker.isdigit():
            raise tasks.InputError("Choose a task to wait on")
        tasks.add_dependency(connection, task_id, int(blocker), now(request))
    return await _task_change(request, connection, task_id, change)


@router.post("/tasks/{task_id}/dependencies/{blocked_by_id}/delete")
async def remove_dependency(task_id: int, blocked_by_id: int, request: Request, connection=Depends(get_db)):
    tasks.remove_dependency(connection, task_id, blocked_by_id, now(request))
    return redirect(f"/tasks/{task_id}")


@router.get("/projects")
def projects(request: Request, connection=Depends(get_db)):
    return render(request, "projects.html", projects=tasks.list_projects(connection))


@router.post("/projects")
async def create_project(request: Request, connection=Depends(get_db)):
    form = await request.form()
    try:
        data = tasks.ProjectIn(name=form.get("name", ""), private=form.get("private") == "on")
        tasks.create_project(connection, data, now(request))
    except FAILURES as error:
        return render(request, "projects.html", 400, error=describe(error),
                      projects=tasks.list_projects(connection))
    return redirect("/projects")


def settings_context(request, connection):
    return {"backups": storage.list_backups(request.app.state.settings.backup_dir),
            "data_dir": request.app.state.settings.data_dir, "weights": priorities.get_weights(connection),
            "defaults": priorities.DEFAULT_WEIGHTS, "schedule": scheduler.get_schedule(connection)}


@router.post("/settings/schedule")
async def save_schedule(request: Request, connection=Depends(get_db)):
    form = await request.form()
    try:
        scheduler.set_schedule(connection, scheduler.Schedule(morning=form.get("morning", ""),
                                                              evening=form.get("evening", "")))
    except FAILURES as error:
        return render(request, "settings.html", 400, error=describe(error), **settings_context(request, connection))
    return redirect("/settings")


@router.get("/settings")
def settings_page(request: Request, connection=Depends(get_db)):
    return render(request, "settings.html", **settings_context(request, connection))


@router.post("/settings/weights")
async def save_weights(request: Request, connection=Depends(get_db)):
    form = await request.form()
    try:
        values = {factor: form.get(factor) for factor in priorities.FACTORS}
        weights = priorities.Weights() if form.get("reset") else priorities.Weights(**values)
        priorities.set_weights(connection, weights)
    except FAILURES as error:
        return render(request, "settings.html", 400, error=describe(error), **settings_context(request, connection))
    return redirect("/settings")


@router.post("/settings/backup")
def backup_now(request: Request, connection=Depends(get_db)):
    try:
        storage.backup(connection, request.app.state.settings.backup_dir, now(request))
    except tasks.InputError as error:
        return render(request, "settings.html", 400, error=str(error), **settings_context(request, connection))
    return redirect("/settings")
