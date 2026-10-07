"""FastAPI application: server-rendered pages and a JSON API on 127.0.0.1."""
import asyncio
from contextlib import asynccontextmanager, closing, suppress
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .ai import Gateway, OllamaProvider
from .config import Settings, load_settings, prepare
from .db import connect, migrate
from .security import LocalGuard, csrf_token, require_csrf
from .tasks import InputError, NotFound

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


def local_now() -> datetime:
    return datetime.now().astimezone()


def get_db(request: Request):
    with closing(connect(request.app.state.settings.database)) as connection:
        yield connection


def now(request: Request) -> datetime:
    return request.app.state.clock()


def today(request: Request):
    return now(request).date()


def render(request: Request, name: str, status_code: int = 200, **context):
    context.update(csrf_token=csrf_token(request), now=now(request))
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def describe(error: Exception) -> str:
    if isinstance(error, ValidationError):
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "input"
        return f"{field.replace('_', ' ')}: {first['msg']}"
    return str(error)


def create_app(settings: Settings = None, clock=local_now, run_scheduler: bool = True) -> FastAPI:
    from . import api, pages, scheduler

    settings = settings or load_settings()
    secret = prepare(settings)
    with closing(connect(settings.database)) as connection:
        migrate(connection)

    @asynccontextmanager
    async def lifespan(app):
        background = None
        if run_scheduler:
            await asyncio.to_thread(scheduler.run_once, app)  # catch up on anything missed while closed
            background = asyncio.create_task(scheduler.run_forever(app))
        yield
        if background:
            background.cancel()
            with suppress(asyncio.CancelledError):
                await background

    app = FastAPI(title="Productivity Assistant", dependencies=[Depends(require_csrf)], lifespan=lifespan)
    app.state.settings, app.state.secret, app.state.clock = settings, secret, clock
    app.state.gateway = Gateway(None if settings.ai_model == "off" else OllamaProvider(settings.ai_model))
    app.add_middleware(LocalGuard, port=settings.port)
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    app.include_router(api.router, prefix="/api")
    app.include_router(pages.router)

    @app.exception_handler(InputError)
    def input_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(NotFound)
    def not_found(request, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    return app
