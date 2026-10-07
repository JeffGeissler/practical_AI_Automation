"""Export (JSON and CSV) and SQLite backups with rotation, verification and restore."""
import csv
import io
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .tasks import InputError, stamp

EXPORT_FORMAT = "productivity-assistant-export/1"
BACKUP_GLOB = "assistant-*.sqlite"


def export_data(connection, now) -> dict:
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {"format": EXPORT_FORMAT, "exported_at": stamp(now),
            "tables": {table: [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]
                       for table in tables}}


def _cell(value):
    # Spreadsheets run cells starting with these characters as formulas.
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def export_tasks_csv(connection) -> str:
    columns = ["id", "title", "status", "due_date", "importance", "effort_minutes", "project", "notes",
               "source", "created_at", "completed_at"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in connection.execute(
            "SELECT t.id, t.title, t.status, t.due_date, t.importance, t.effort_minutes, p.name, t.notes, "
            "t.source, t.created_at, t.completed_at FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
            "WHERE t.deleted_at IS NULL ORDER BY t.id"):
        writer.writerow([_cell(value) for value in row])
    return output.getvalue()


def backup(connection, folder: Path, now, keep: int = 14) -> Path:
    """Write a consistent single-file copy (no WAL sidecars) and keep the newest `keep` backups."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / f"assistant-{now.strftime('%Y%m%d-%H%M%S')}.sqlite"
    if target.exists():
        raise InputError("A backup was already made this second")
    connection.execute("VACUUM INTO ?", (str(target),))
    os.chmod(target, 0o600)
    for old in list_backups(folder)[keep:]:
        old.unlink()
    return target


def list_backups(folder: Path) -> list:
    return sorted(folder.glob(BACKUP_GLOB), reverse=True) if folder.is_dir() else []


def verify_backup(path: Path) -> dict:
    try:
        with closing(_read_only(path)) as source:
            integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
            version = source.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
            tasks = source.execute("SELECT count(*) FROM tasks WHERE deleted_at IS NULL").fetchone()[0]
    except sqlite3.DatabaseError as error:
        raise InputError(f"Not a usable backup: {error}") from None
    if integrity != "ok":
        raise InputError(f"Backup failed its integrity check: {integrity}")
    return {"path": str(path), "schema_version": version, "tasks": tasks}


def _read_only(path: Path):
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def restore(path: Path, database: Path, backup_dir: Path, now) -> Path:
    """Replace the database with a verified backup; the current state is backed up first.

    Stop the app before restoring from the command line."""
    verify_backup(path)
    with closing(sqlite3.connect(database)) as current:
        safety = backup(current, backup_dir, now, keep=10**6)
        with closing(_read_only(path)) as source:
            source.backup(current)
    return safety
