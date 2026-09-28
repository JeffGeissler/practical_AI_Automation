"""SQLite connection and versioned migrations (migrations/NNN_name.sql, applied in order)."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS = Path(__file__).with_name("migrations")


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def migrate(connection: sqlite3.Connection) -> list:
    connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                       "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    new = []
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
        version = int(path.name[:3])
        if version in applied:
            continue
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # executescript commits first; BEGIN/COMMIT make each migration all-or-nothing.
        connection.executescript(
            f"BEGIN;\n{path.read_text()}\n"
            f"INSERT INTO schema_migrations VALUES ({version}, '{path.stem}', '{stamp}');\nCOMMIT;")
        new.append(path.stem)
    return new
