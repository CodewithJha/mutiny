"""ASGI application object for the Hosted API.

Prefer the supported process entrypoint ``python -m mutiny_api`` (see
``mutiny_api.serve``) so non-loopback binds fail closed without
``MUTINY_API_TOKEN`` before listen (P0-1 / P0-4).

Raw ``uvicorn mutiny_api.main:app --host …`` remains valid for ASGI tooling
and tests, but Mutiny-supported deploy/dev scripts use ``python -m mutiny_api``.

Database path: ``MUTINY_DB_PATH`` if set, else ``data/mutiny.sqlite``.
See ``mutiny_api.db.resolve_db_path``.
"""

from mutiny_api.app import create_app

app = create_app()
