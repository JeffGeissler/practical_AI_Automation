"""FastAPI application: server-rendered pages and a JSON API on 127.0.0.1."""
from contextlib import closing
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Settings, load_settings, prepare
from .db import connect, migrate
from .security import LocalGuard, csrf_token, require_csrf

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


def local_now() -> datetime:
    return datetime.now().astimezone()


def get_db(request: Request):
    with closing(connect(request.app.state.settings.database)) as connection:
        yield connection


def render(request: Request, name: str, status_code: int = 200, **context):
    context.update(csrf_token=csrf_token(request), now=request.app.state.clock())
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def create_app(settings: Settings = None, clock=local_now) -> FastAPI:
    settings = settings or load_settings()
    secret = prepare(settings)
    with closing(connect(settings.database)) as connection:
        migrate(connection)
    app = FastAPI(title="Productivity Assistant", dependencies=[Depends(require_csrf)])
    app.state.settings, app.state.secret, app.state.clock = settings, secret, clock
    app.add_middleware(LocalGuard, port=settings.port)
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/api/csrf")
    def csrf(request: Request):
        """Token for API clients on this Mac; other sites cannot read it (no CORS)."""
        return {"csrf_token": csrf_token(request)}

    @app.get("/")
    def today(request: Request):
        return render(request, "today.html")

    @app.put("/api/settings/{key}")
    def put_setting(key: str, body: dict, connection=Depends(get_db)):
        value = str(body.get("value", ""))
        with connection:
            connection.execute("INSERT INTO settings VALUES (?, ?) "
                               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
        return {"key": key, "value": value}

    return app
