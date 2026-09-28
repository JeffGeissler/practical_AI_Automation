"""Command line: `productivity-assistant` serves the app on 127.0.0.1 only."""
import argparse

import uvicorn

from .config import load_settings
from .web import create_app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="productivity-assistant")
    parser.parse_args(argv)
    settings = load_settings()
    print(f"Data folder: {settings.data_dir}\nOpen http://127.0.0.1:{settings.port}/")
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, access_log=False)


if __name__ == "__main__":
    main()
