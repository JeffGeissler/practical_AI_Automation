"""Command line: serve the app on 127.0.0.1 only, back up, or restore a backup."""
import argparse
from contextlib import closing
from pathlib import Path

from .config import load_settings, prepare
from .db import connect, migrate
from .storage import backup, restore, verify_backup
from .web import local_now


def main(argv=None):
    parser = argparse.ArgumentParser(prog="productivity-assistant")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="run the app (default)")
    commands.add_parser("backup", help="write a backup now")
    restoring = commands.add_parser("restore", help="replace the database with a backup; stop the app first")
    restoring.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "backup":
        prepare(settings)
        with closing(connect(settings.database)) as connection:
            migrate(connection)
            print(verify_backup(backup(connection, settings.backup_dir, local_now())))
    elif args.command == "restore":
        safety = restore(args.file, settings.database, settings.backup_dir, local_now())
        print(f"Restored {args.file}. The previous state was saved as {safety}")
    else:
        import uvicorn

        from .web import create_app
        print(f"Data folder: {settings.data_dir}\nOpen http://127.0.0.1:{settings.port}/")
        uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, access_log=False)


if __name__ == "__main__":
    main()
