"""Ensure examples/openai_support_agent/.mutiny/adapter.py exists (Railway/Hosted).

``.mutiny/`` is gitignored for customer projects; Docker also cannot re-include
paths under an excluded ``.mutiny/`` parent. This script writes the sample
adapter at container start if the file is missing.
"""

from __future__ import annotations

from pathlib import Path

ADAPTER = '''\
"""Mutiny adapter wiring for the Acme Support sample project.

Loaded by Hosted / CLI via ``create_adapter()`` — same path as any customer
OpenAI Agents SDK project.
"""

from __future__ import annotations

from mutiny_openai_agents import OpenAIAgentsAdapter


def create_adapter(*, enforce_refund_policy: bool = False) -> OpenAIAgentsAdapter:
    """Factory used by Hosted and ``mutiny run``.

    ``enforce_refund_policy=True`` is the regression PASS / fixed-agent path.
    """
    from agent import build_agent
    from tools import CUSTOMER_CONTEXT, reset_tool_state

    return OpenAIAgentsAdapter(
        agent=build_agent(enforce_refund_policy=enforce_refund_policy),
        context=CUSTOMER_CONTEXT,
        on_reset=reset_tool_state,
    )
'''

INIT = '"""Mutiny project scaffolding for the sample OpenAI Agents SDK agent."""\n'


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    mutiny_dir = root / "examples" / "openai_support_agent" / ".mutiny"
    mutiny_dir.mkdir(parents=True, exist_ok=True)
    init_py = mutiny_dir / "__init__.py"
    adapter = mutiny_dir / "adapter.py"
    if not init_py.exists():
        init_py.write_text(INIT, encoding="utf-8")
        print(f"wrote {init_py}")
    if not adapter.exists():
        adapter.write_text(ADAPTER, encoding="utf-8")
        print(f"wrote {adapter}")
    else:
        print(f"ok {adapter}")


if __name__ == "__main__":
    main()
