#!/usr/bin/env python3
"""Refresh README contributors gallery from the GitHub Contributors API."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "CodewithJha/mutiny")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
README_PATH = os.environ.get("README_PATH", "README.md")
COLUMNS = int(os.environ.get("CONTRIBUTORS_COLUMNS", "6"))
IMAGE_SIZE = int(os.environ.get("CONTRIBUTORS_IMAGE_SIZE", "100"))

START = "<!-- contributors-gallery:start -->"
END = "<!-- contributors-gallery:end -->"


def fetch_contributors() -> list[dict]:
    url = f"https://api.github.com/repos/{REPO}/contributors?per_page=100&anon=false"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "mutiny-contributors-gallery",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected contributors payload: {data!r}")
    return [c for c in data if c.get("type") == "User" and c.get("login")]


def render_table(contributors: list[dict]) -> str:
    cells: list[str] = []
    for c in contributors:
        login = c["login"]
        avatar = c.get("avatar_url") or f"https://github.com/{login}.png"
        sep = "&" if "?" in avatar else "?"
        avatar = f"{avatar}{sep}s={IMAGE_SIZE}"
        profile = c.get("html_url") or f"https://github.com/{login}"
        cells.append(
            "\n".join(
                [
                    '            <td align="center">',
                    f'                <a href="{profile}">',
                    f'                    <img src="{avatar}" width="{IMAGE_SIZE}" height="{IMAGE_SIZE}" alt="{login}"/>',
                    "                    <br />",
                    f"                    <sub><b>{login}</b></sub>",
                    "                </a>",
                    "            </td>",
                ]
            )
        )

    rows: list[str] = []
    for i in range(0, len(cells), COLUMNS):
        chunk = "\n".join(cells[i : i + COLUMNS])
        rows.append(f"        <tr>\n{chunk}\n        </tr>")

    body = "\n".join(rows) if rows else "        <tr></tr>"
    return (
        f"{START}\n"
        "<table>\n"
        "    <tbody>\n"
        f"{body}\n"
        "    </tbody>\n"
        "</table>\n"
        f"{END}"
    )


def main() -> int:
    contributors = fetch_contributors()
    if not contributors:
        print("No contributors returned; leaving README unchanged.", file=sys.stderr)
        return 0

    block = render_table(contributors)
    text = open(README_PATH, encoding="utf-8").read()

    if START in text and END in text:
        pattern = re.compile(
            re.escape(START) + r".*?" + re.escape(END),
            flags=re.DOTALL,
        )
        new_text, n = pattern.subn(block, text, count=1)
        if n != 1:
            raise SystemExit("Failed to replace contributors gallery markers")
    else:
        # Migrate from the previous action markers if present.
        legacy = re.compile(
            r"<!-- readme: contributors -start -->.*?<!-- readme: contributors -end -->",
            flags=re.DOTALL,
        )
        new_text, n = legacy.subn(block, text, count=1)
        if n != 1:
            raise SystemExit(
                "README is missing contributors-gallery markers; add "
                f"{START} / {END} under ## Contributors"
            )

    if new_text == text:
        print("README contributors gallery already up to date.")
        return 0

    open(README_PATH, "w", encoding="utf-8").write(new_text)
    print(
        "Updated README contributors:",
        ", ".join(c["login"] for c in contributors),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
