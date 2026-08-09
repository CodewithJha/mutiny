"""CLI entrypoint: ``mutiny init`` / ``mutiny run`` / ``mutiny test``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mutiny",
        description=(
            "Mutiny — behavioral fuzz-testing engine for AI agents. "
            "Commands: init, run, test."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser(
        "init",
        help="Scaffold .mutiny/adapter.py, policy.yaml, mutiny.yaml",
    )
    init_p.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd)",
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing scaffold files",
    )

    run_p = sub.add_parser(
        "run",
        help="Load adapter + policy and start a campaign",
    )
    run_p.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd)",
    )
    run_p.add_argument(
        "--hosted-url",
        default=None,
        help="Hosted API base URL (overrides mutiny.yaml)",
    )
    run_p.add_argument(
        "--no-hosted",
        action="store_true",
        help="Skip Hosted API registration; run locally only",
    )
    run_p.add_argument(
        "--attestation",
        action="store_true",
        default=True,
        help="Confirm authorized testing (default: true)",
    )

    test_p = sub.add_parser(
        "test",
        help=(
            "Replay project regressions under .mutiny/tests/ "
            "(PASS/FAIL/SKIPPED report)"
        ),
    )
    test_p.add_argument(
        "regression_id",
        nargs="?",
        default=None,
        help="Optional regression id or name (default: run all)",
    )
    test_p.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd)",
    )
    test_p.add_argument(
        "--failed",
        action="store_true",
        help="Re-run only cases that failed in the last .mutiny/test-report.json",
    )
    test_p.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="Print structured JSON report to stdout",
    )
    test_p.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write .mutiny/test-report.json",
    )

    args = parser.parse_args(argv)
    if args.command == "init":
        from mutiny_cli.init_cmd import run_init

        return run_init(project_root=args.path, force=args.force)
    if args.command == "run":
        from mutiny_cli.run_cmd import run_campaign

        return run_campaign(
            project_root=args.path,
            hosted_url=args.hosted_url,
            no_hosted=args.no_hosted,
            attestation=args.attestation,
        )
    if args.command == "test":
        from mutiny_cli.test_cmd import run_tests

        return run_tests(
            project_root=args.path,
            regression_id=args.regression_id,
            failed_only=args.failed,
            json_out=args.json_out,
            write_report=not args.no_report,
        )
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
