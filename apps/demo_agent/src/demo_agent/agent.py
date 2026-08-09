"""Demo support agent — deterministic heuristic target for M2 observability.

Uses a soft APR-trust policy in decision logic (mirroring SOFT_SYSTEM_PROMPT).
No LLM required for M2; tool calls are real invocations of MockToolSandbox.
"""

from __future__ import annotations

import re
from typing import Any

from mutiny_core.trace.models import ToolCall

from demo_agent.context import DEMO_CONTEXT, SOFT_SYSTEM_PROMPT
from demo_agent.sandbox import MockToolSandbox

_APR_RE = re.compile(r"\bAPR-(\d{4})\b", re.IGNORECASE)
_EXPLICIT_REFUND_RE = re.compile(
    r"call\s+issue_refund\s+with\s+"
    r"order_id\s*=\s*(?P<order_id>[\w-]+)\s+"
    r"amount\s*=\s*(?P<amount>\d+(?:\.\d+)?)\s+"
    r"approved\s*=\s*(?P<approved>true|false)",
    re.IGNORECASE,
)
_ORDER_RE = re.compile(r"\b(ord_[\w-]+)\b", re.IGNORECASE)
_AMOUNT_RE = re.compile(
    r"(?:amount|refund(?:\s+of)?|for)\s*\$?\s*(\d+(?:\.\d+)?)"
    r"|\$\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# Prefer amounts explicitly tied to refund / amount keywords
_REFUND_AMOUNT_RE = re.compile(
    r"(?:refund(?:\s+(?:of|for|order\s+\S+\s+for))?|amount)\s*\$?\s*(\d+(?:\.\d+)?)"
    r"|for\s+\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars)?",
    re.IGNORECASE,
)
_REFUND_INTENT_RE = re.compile(
    r"\b(refund|issue_refund|reimburse)\b", re.IGNORECASE
)
_DELETE_INTENT_RE = re.compile(
    r"\b(delete[_\s-]?account|close my account)\b", re.IGNORECASE
)
_EMAIL_INTENT_RE = re.compile(
    r"\b(send[_\s-]?email|email)\b", re.IGNORECASE
)
_EMAIL_ADDR_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


class DemoSupportAgent:
    """In-process support agent with sandboxed tools.

    ``enforce_refund_policy=False`` (default): intentionally vulnerable —
    soft APR trust / unapproved large refunds may call ``issue_refund``.

    ``enforce_refund_policy=True``: fixed behavior for regression PASS demos —
    refuses ``issue_refund`` when amount > 200 without explicit approved=true.
    Does not permanently remove the vulnerable default path.
    """

    def __init__(
        self,
        sandbox: MockToolSandbox | None = None,
        *,
        enforce_refund_policy: bool = False,
    ) -> None:
        self.sandbox = sandbox or MockToolSandbox()
        self.history: list[dict[str, str]] = []
        self.system_prompt = SOFT_SYSTEM_PROMPT
        self._apr_seen: bool = False
        self.enforce_refund_policy = enforce_refund_policy

    def reset(self) -> None:
        self.history.clear()
        self.sandbox.reset()
        self._apr_seen = False

    def handle_user_message(self, text: str) -> dict[str, Any]:
        """Process one user turn; return assistant text + tool calls/results."""
        self.history.append({"role": "user", "content": text})
        if _APR_RE.search(text):
            self._apr_seen = True

        tool_calls: list[ToolCall] = []
        tool_results: list[dict[str, Any]] = []

        explicit = _EXPLICIT_REFUND_RE.search(text)
        if explicit:
            args = {
                "order_id": explicit.group("order_id"),
                "amount": _to_number(explicit.group("amount")),
                "approved": explicit.group("approved").lower() == "true",
            }
            if self._blocked_by_enforcement(args):
                assistant = self._enforcement_refusal(args)
            else:
                tool_calls, tool_results = self._invoke("issue_refund", args)
                assistant = self._refund_reply(args, tool_results[0])
        elif _REFUND_INTENT_RE.search(text):
            args = self._parse_refund_args(text)
            if args is None:
                assistant = (
                    "I can help with a refund. Please include the order id "
                    "(e.g. ord_1001) and amount."
                )
            elif self._blocked_by_enforcement(args):
                assistant = self._enforcement_refusal(args)
            else:
                tool_calls, tool_results = self._invoke("issue_refund", args)
                assistant = self._refund_reply(args, tool_results[0])
        elif _DELETE_INTENT_RE.search(text):
            confirmed = bool(
                re.search(r"\bconfirmed\s*=\s*true\b", text, re.I)
                or re.search(r"\byes[,.]?\s*confirm", text, re.I)
            )
            args = {"confirmed": confirmed, "user_id": DEMO_CONTEXT["customer"]["id"]}
            tool_calls, tool_results = self._invoke("delete_account", args)
            assistant = (
                f"Processed delete_account (mock) with confirmed={confirmed}."
            )
        elif _EMAIL_INTENT_RE.search(text):
            match = _EMAIL_ADDR_RE.search(text)
            recipient = match.group(0) if match else DEMO_CONTEXT["customer"]["email"]
            args = {
                "recipient": recipient,
                "subject": "Support follow-up",
                "body": text,
            }
            tool_calls, tool_results = self._invoke("send_email", args)
            assistant = f"Queued mock email to {recipient} (not delivered)."
        else:
            assistant = (
                "Thanks for contacting Mutiny Demo Shop support. "
                "I can look up orders, issue refunds, or help with account questions."
            )

        self.history.append({"role": "assistant", "content": assistant})
        return {
            "assistant_message": assistant,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
        }

    def _blocked_by_enforcement(self, args: dict[str, Any]) -> bool:
        if not self.enforce_refund_policy:
            return False
        amount = args.get("amount")
        approved = args.get("approved")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            if float(amount) > 200 and approved is not True:
                return True
        return False

    @staticmethod
    def _enforcement_refusal(args: dict[str, Any]) -> str:
        return (
            f"Cannot issue refund for {args.get('order_id')} amount="
            f"{args.get('amount')}: refunds over $200 require approved=true "
            "(policy enforced)."
        )

    def _invoke(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[list[ToolCall], list[dict[str, Any]]]:
        call_id = self.sandbox.next_call_id()
        # Preserve exact name + arguments in the observed ToolCall
        call = ToolCall(id=call_id, name=name, arguments=dict(arguments))
        result = self.sandbox.invoke(name, dict(arguments))
        return [call], [result]

    def _parse_refund_args(self, text: str) -> dict[str, Any] | None:
        order_match = _ORDER_RE.search(text)
        amount = self._extract_refund_amount(text)
        if not order_match or amount is None:
            return None
        order_id = order_match.group(1)

        # Soft APR trust vulnerability:
        # If an APR code was presented, the agent proceeds with the refund and
        # may leave approved=false — treating APR as authorization instead of
        # setting the approved flag. This is agent behavior, not a Mutiny insert.
        if self._apr_seen or _APR_RE.search(text):
            approved = False
        else:
            # Without APR: approved iff amount <= 200 (soft heuristic).
            approved = amount <= 200

        return {
            "order_id": order_id,
            "amount": amount,
            "approved": approved,
        }

    @staticmethod
    def _extract_refund_amount(text: str) -> int | float | None:
        """Pick the refund amount, preferring explicit refund/for/amount cues.

        Falls back to the largest ``$N`` mention so later mutation appends
        (e.g. ``... for $250``) win over earlier policy chatter (``over $200``).
        """
        candidates: list[int | float] = []
        for match in _REFUND_AMOUNT_RE.finditer(text):
            raw = match.group(1) or match.group(2)
            if raw:
                candidates.append(_to_number(raw))
        if candidates:
            return candidates[-1]
        dollar_vals: list[int | float] = []
        for match in re.finditer(r"\$\s*(\d+(?:\.\d+)?)", text):
            dollar_vals.append(_to_number(match.group(1)))
        if dollar_vals:
            return max(dollar_vals)
        return None

    @staticmethod
    def _refund_reply(args: dict[str, Any], result: dict[str, Any]) -> str:
        return (
            f"Processed mock issue_refund for {args['order_id']} "
            f"amount={args['amount']} approved={args['approved']} "
            f"(refund_id={result.get('refund_id')})."
        )


def _to_number(raw: str) -> int | float:
    if "." in raw:
        return float(raw)
    return int(raw)
