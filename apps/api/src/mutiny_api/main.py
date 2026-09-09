"""ASGI entrypoint: ``uvicorn mutiny_api.main:app``.

Database path: ``MUTINY_DB_PATH`` if set, else ``data/mutiny.sqlite``.
See ``mutiny_api.db.resolve_db_path``.
"""

from mutiny_api.app import create_app

app = create_app()
