"""Settings from the environment. Private state must live outside the source tree."""
import os
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "ProductivityAssistant"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int = 8000

    @property
    def database(self) -> Path:
        return self.data_dir / "assistant.sqlite"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"


def load_settings(environ=os.environ) -> Settings:
    data_dir = Path(environ.get("PA_DATA_DIR") or DEFAULT_DATA_DIR).expanduser().resolve()
    if data_dir == REPOSITORY or REPOSITORY in data_dir.parents:
        raise ValueError(f"PA_DATA_DIR must be outside the source tree ({REPOSITORY})")
    port = int(environ.get("PA_PORT", "8000"))
    if not 1024 <= port <= 65535:
        raise ValueError("PA_PORT must be between 1024 and 65535")
    return Settings(data_dir=data_dir, port=port)


def prepare(settings: Settings) -> bytes:
    """Create private folders and return the session secret (created once, owner-only)."""
    for folder in (settings.data_dir, settings.backup_dir):
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    secret_path = settings.data_dir / "session.key"
    try:
        descriptor = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return secret_path.read_bytes()
    with os.fdopen(descriptor, "wb") as handle:
        secret = os.urandom(32)
        handle.write(secret)
    return secret
