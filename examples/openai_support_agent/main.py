"""Interactive chat for the sample Acme Support Agent."""

from __future__ import annotations

import os
import sys

from agents import Runner
from agents.memory.sqlite_session import SQLiteSession

from agent import support_agent
from tools import reset_tool_state


def main() -> int:
    print("Acme Support Agent (OpenAI Agents SDK sample)")
    print("Type a message, or 'quit' to exit.")
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "(OPENAI_API_KEY unset — using offline SoftSupportScriptedModel; "
            "set MUTINY_SAMPLE_OFFLINE=0 and OPENAI_API_KEY for live models.)"
        )
    reset_tool_state()
    session = SQLiteSession("cli-demo", db_path=":memory:")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            return 0
        result = Runner.run_sync(support_agent, user, session=session)
        print(f"agent> {result.final_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
