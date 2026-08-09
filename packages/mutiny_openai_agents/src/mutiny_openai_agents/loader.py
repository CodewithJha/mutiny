"""Load customer agent modules by ``module:attr`` reference."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def ensure_project_on_path(project_root: str | Path) -> None:
    """Prepend a customer project root to ``sys.path`` for local imports."""
    root = str(Path(project_root).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def load_callable(ref: str) -> Any:
    """Import ``module:attr`` and return the attribute (object or callable)."""
    if ":" not in ref:
        raise ValueError(
            f"invalid ref {ref!r}; expected 'module:attribute' "
            "(e.g. 'agent:support_agent' or 'agent:build_agent')"
        )
    module_name, attr_name = ref.split(":", 1)
    if not module_name or not attr_name:
        raise ValueError(f"invalid ref {ref!r}; module and attribute required")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {module_name!r} has no attribute {attr_name!r}"
        ) from exc


def load_agent_from_ref(ref: str) -> Any:
    """Resolve an OpenAI Agents SDK Agent from ``module:attr``.

    If the attribute is callable (and not already an Agent-like instance with
    ``name`` + ``tools``), it is called with no arguments.
    """
    obj = load_callable(ref)
    if callable(obj) and not _looks_like_agent(obj):
        obj = obj()
    if not _looks_like_agent(obj):
        raise TypeError(
            f"{ref!r} did not resolve to an OpenAI Agents SDK Agent "
            f"(got {type(obj)!r})"
        )
    return obj


def load_adapter_factory(
    project_root: str | Path,
    *,
    module: str = ".mutiny.adapter",
    attr: str = "create_adapter",
) -> Callable[[], Any]:
    """Load ``create_adapter`` from the customer's ``.mutiny/adapter.py``.

    Supports either package-style ``.mutiny.adapter`` (if ``.mutiny`` is a
    package) or a direct file load of ``.mutiny/adapter.py``.
    """
    root = Path(project_root).resolve()
    ensure_project_on_path(root)

    adapter_file = root / ".mutiny" / "adapter.py"
    if not adapter_file.exists():
        raise FileNotFoundError(
            f"missing {adapter_file}; run `mutiny init` first"
        )

    # Load as a unique module from file path so `.mutiny` need not be a package
    spec_name = "mutiny_project_adapter"
    import importlib.util

    spec = importlib.util.spec_from_file_location(spec_name, adapter_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load adapter module from {adapter_file}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec_name] = mod
    spec.loader.exec_module(mod)

    factory = getattr(mod, attr, None)
    if factory is None or not callable(factory):
        raise AttributeError(
            f"{adapter_file} must define callable {attr}() → TargetAdapter"
        )
    return factory  # type: ignore[return-value]


def _looks_like_agent(obj: Any) -> bool:
    return (
        hasattr(obj, "name")
        and hasattr(obj, "tools")
        and not isinstance(obj, type)
    )
