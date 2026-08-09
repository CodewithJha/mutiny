"""ASGI entrypoint: ``uvicorn mutiny_api.main:app``."""

from pathlib import Path

from mutiny_api.app import create_app

app = create_app(Path("data/mutiny.sqlite"))
