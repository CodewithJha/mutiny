"""Packaging / release integrity — versions + wheel surface vs checkout drift."""

from __future__ import annotations

import ast
import re
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PACKAGES = {
    "mutiny-core": REPO / "packages" / "mutiny_core",
    "mutiny-openai-agents": REPO / "packages" / "mutiny_openai_agents",
    "mutiny-ai": REPO / "packages" / "mutiny_cli",
}
_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.M)


def _pyproject_version(pkg_dir: Path) -> str:
    text = (pkg_dir / "pyproject.toml").read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    assert match, f"version missing in {pkg_dir / 'pyproject.toml'}"
    return match.group(1)


def test_publishable_package_versions_aligned() -> None:
    versions = {name: _pyproject_version(path) for name, path in PACKAGES.items()}
    unique = set(versions.values())
    assert len(unique) == 1, f"publishable package versions diverge: {versions}"
    assert next(iter(unique)), "empty version"


def test_sibling_dependency_floors_match_release_line() -> None:
    """CLI/adapter must not accept stale 0.1.x cores when this line is ≥0.2."""
    release = _pyproject_version(PACKAGES["mutiny-core"])
    major_minor = ".".join(release.split(".")[:2])
    floor = f"{major_minor}.0" if major_minor.count(".") == 1 else release
    cli_text = (PACKAGES["mutiny-ai"] / "pyproject.toml").read_text(encoding="utf-8")
    openai_text = (PACKAGES["mutiny-openai-agents"] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert f"mutiny-core>={floor}" in cli_text or f"mutiny-core>={release}" in cli_text
    assert (
        f"mutiny-openai-agents>={floor}" in cli_text
        or f"mutiny-openai-agents>={release}" in cli_text
    )
    assert (
        f"mutiny-core>={floor}" in openai_text
        or f"mutiny-core>={release}" in openai_text
    )


def test_runtime_version_matches_mutiny_core_metadata() -> None:
    from mutiny_core import __version__

    assert __version__ == _pyproject_version(PACKAGES["mutiny-core"])
    # Must not be a stale hardcode when metadata differs
    assert not __version__.startswith("0.0.0+"), (
        "mutiny_core.__version__ fell back to local placeholder; "
        "install workspace packages (uv sync) so importlib.metadata resolves"
    )


def test_built_wheels_contain_current_surface(tmp_path: Path) -> None:
    """Build wheels and assert the stale-PyPI failure class cannot hide."""
    import subprocess

    out = tmp_path / "dist"
    for name, pkg in (
        ("core", PACKAGES["mutiny-core"]),
        ("openai", PACKAGES["mutiny-openai-agents"]),
        ("cli", PACKAGES["mutiny-ai"]),
    ):
        target = out / name
        target.mkdir(parents=True)
        subprocess.run(
            ["uv", "build", "--out-dir", str(target), str(pkg)],
            check=True,
            cwd=REPO,
        )

    core_whl = next((out / "core").glob("mutiny_core-*-py3-none-any.whl"))
    openai_whl = next((out / "openai").glob("mutiny_openai_agents-*-py3-none-any.whl"))
    cli_whl = next((out / "cli").glob("mutiny_ai-*-py3-none-any.whl"))

    with zipfile.ZipFile(core_whl) as z:
        names = set(z.namelist())
        assert "mutiny_core/redact.py" in names
        assert not any("__pycache__" in n for n in names)
        assert not any(n.endswith(".pyc") for n in names)

    with zipfile.ZipFile(cli_whl) as z:
        names = set(z.namelist())
        assert "mutiny_cli/db_cmd.py" in names
        assert "mutiny_cli/run_cmd.py" in names
        run_src = z.read("mutiny_cli/run_cmd.py").decode("utf-8")
        # Compile catches SyntaxError class of stale release (historical PyPI gap)
        ast.parse(run_src)
        assert "population_size" in run_src
        assert "no_hosted" in run_src

    with zipfile.ZipFile(openai_whl) as z:
        names = set(z.namelist())
        assert "mutiny_openai_agents/adapter.py" in names
        assert not any(
            part in n for n in names for part in ("/tests/", "apps/", "examples/")
        )


def test_sample_project_root_requires_repo_when_not_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mutiny_openai_agents import sample as sample_mod

    fake = tmp_path / "site-packages" / "mutiny_openai_agents" / "sample.py"
    fake.parent.mkdir(parents=True)
    fake.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(sample_mod, "__file__", str(fake))
    with pytest.raises(FileNotFoundError, match="repo_root"):
        sample_mod.sample_project_root()
