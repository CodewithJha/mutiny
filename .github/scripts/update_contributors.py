#!/usr/bin/env python3
"""Refresh README contributors gallery from GitHub commit authors.

Uses the Commits API (not /contributors). GitHub's contributors-stats cache
is often incomplete for minutes–days after a merge; Actions runners can see a
stale subset while public curls already show everyone. Commit authors are the
attribution source of truth for squash merges.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter

REPO = os.environ.get("GITHUB_REPOSITORY", "CodewithJha/mutiny")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
README_PATH = os.environ.get("README_PATH", "README.md")
COLUMNS = int(os.environ.get("CONTRIBUTORS_COLUMNS", "6"))
IMAGE_SIZE = int(os.environ.get("CONTRIBUTORS_IMAGE_SIZE", "100"))

START = "<!-- contributors-gallery:start -->"
END = "<!-- contributors-gallery:end -->"


def api_get(path: str) -> object:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "mutiny-contributors-gallery",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def is_bot(login: str) -> bool:
    lower = login.lower()
    return lower.endswith("[bot]") or lower in {"github-actions[bot]", "dependabot[bot]"}


def fetch_commit_authors() -> list[str]:
    """Unique GitHub logins from commit.author, most commits first."""
    counts: Counter[str] = Counter()
    page = 1
    while page <= 20:
        data = api_get(f"/repos/{REPO}/commits?per_page=100&page={page}")
        if not isinstance(data, list) or not data:
            break
        for commit in data:
            author = commit.get("author") or {}
            login = author.get("login")
            if login and not is_bot(login):
                counts[login] += 1
        if len(data) < 100:
            break
        page += 1
    return [login for login, _ in counts.most_common()]


def render_table(logins: list[str]) -> str:
    cells: list[str] = []
    for login in logins:
        profile = f"https://github.com/{login}"
        # github.com/<user>.png is a stable avatar redirect; size via s=.
        avatar = f"https://github.com/{login}.png?size={IMAGE_SIZE}"
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


def replace_gallery(text: str, block: str) -> str:
    if START in text and END in text:
        pattern = re.compile(
            re.escape(START) + r".*?" + re.escape(END),
            flags=re.DOTALL,
        )
        new_text, n = pattern.subn(block, text, count=1)
        if n != 1:
            raise SystemExit("Failed to replace contributors-gallery markers")
        return new_text

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
    return new_text


def main() -> int:
    try:
        logins = fetch_commit_authors()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GitHub API error: {exc.code} {exc.reason}") from exc

    if not logins:
        print("No commit authors found; leaving README unchanged.", file=sys.stderr)
        return 0

    block = render_table(logins)
    text = open(README_PATH, encoding="utf-8").read()
    new_text = replace_gallery(text, block)

    if new_text == text:
        print("README contributors gallery already up to date:", ", ".join(logins))
        return 0

    open(README_PATH, "w", encoding="utf-8").write(new_text)
    print("Updated README contributors:", ", ".join(logins))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
