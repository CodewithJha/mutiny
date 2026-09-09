"""Supported Mutiny Hosted API process entrypoint (P0-1 / P0-4).

Use ``python -m mutiny_api`` (this module) instead of raw
``uvicorn mutiny_api.main:app --host …`` so non-loopback binds fail closed
before the server socket listens when ``MUTINY_API_TOKEN`` is missing.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from mutiny_api.bind_security import (
    BindSecurityError,
    require_token_for_non_loopback_bind,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mutiny_api",
        description=(
            "Start the Mutiny Hosted API. Non-loopback binds require "
            "MUTINY_API_TOKEN."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind host (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind port (default: {DEFAULT_PORT})",
    )
    return parser


def run_server(*, host: str, port: int) -> None:
    """Validate bind auth posture, then hand off to uvicorn.

    Raises ``BindSecurityError`` before ``uvicorn.run`` when a non-loopback
    host is used without a usable token — the listen socket is never opened.
    """
    require_token_for_non_loopback_bind(host)
    import uvicorn

    uvicorn.run("mutiny_api.main:app", host=host, port=port)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    try:
        run_server(host=args.host, port=args.port)
    except BindSecurityError as exc:
        print(f"mutiny_api: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
