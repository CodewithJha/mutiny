"""Deliberately vulnerable demo support agent — mock tools only.

Not a Mutiny campaign engine. Soft APR-trust behavior lives here so Mutiny
can observe real tool calls; Mutiny never inserts synthetic violations.
"""

from demo_agent.adapter import InProcessDemoAdapter
from demo_agent.agent import DemoSupportAgent
from demo_agent.context import DEMO_CONTEXT
from demo_agent.sandbox import MockToolSandbox

__all__ = [
    "DEMO_CONTEXT",
    "DemoSupportAgent",
    "InProcessDemoAdapter",
    "MockToolSandbox",
]

__version__ = "0.1.0"
