"""In-app scheduler. Runs while the app runs, and catches up on startup for anything missed today.

Each job checks stored results before running, so repeated checks (every minute, after a
restart or a crash) never produce a second scheduled briefing or backup for the same day.
"""
import asyncio
import json
import logging
from contextlib import closing
from datetime import datetime, time, timedelta

from pydantic import BaseModel, ConfigDict, Field

from . import briefings, storage
from .db import connect

log = logging.getLogger(__name__)
CHECK_SECONDS = 60
ON_TIME = timedelta(minutes=10)
TIME_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    morning: str = Field("08:00", pattern=TIME_PATTERN)
    evening: str = Field("18:00", pattern=TIME_PATTERN)


def get_schedule(connection) -> Schedule:
    row = connection.execute("SELECT value FROM settings WHERE key = 'schedule'").fetchone()
    return Schedule(**json.loads(row[0])) if row else Schedule()


def set_schedule(connection, schedule: Schedule):
    with connection:
        connection.execute("INSERT INTO settings VALUES ('schedule', ?) "
                           "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (schedule.model_dump_json(),))


def run_due_jobs(connection, backup_dir, now: datetime) -> list:
    """Run whatever is due and not yet done today; returns what ran, e.g. ['morning:catch_up', 'backup']."""
    today, ran = now.date(), []
    schedule = get_schedule(connection)
    for kind in ("morning", "evening"):
        planned = datetime.combine(today, time.fromisoformat(getattr(schedule, kind)), now.tzinfo)
        if now < planned:
            continue
        done = connection.execute("SELECT 1 FROM briefings WHERE kind = ? AND day = ? AND trigger != 'manual'",
                                  (kind, today.isoformat())).fetchone()
        if not done:
            trigger = "schedule" if now - planned <= ON_TIME else "catch_up"
            briefings.generate(connection, kind, now, trigger)
            ran.append(f"{kind}:{trigger}")
    prefix = f"assistant-{today.strftime('%Y%m%d')}-"
    if not any(path.name.startswith(prefix) for path in storage.list_backups(backup_dir)):
        storage.backup(connection, backup_dir, now)
        ran.append("backup")
    return ran


def run_once(app) -> list:
    settings = app.state.settings
    try:
        with closing(connect(settings.database)) as connection:
            ran = run_due_jobs(connection, settings.backup_dir, app.state.clock())
    except Exception:  # keep the app running; the next check retries
        log.exception("Scheduled jobs failed")
        return []
    if ran:
        log.info("Scheduled jobs ran: %s", ", ".join(ran))
    return ran


async def run_forever(app):
    while True:
        await asyncio.sleep(CHECK_SECONDS)
        await asyncio.to_thread(run_once, app)
