"""In-memory mock tools — never perform real side effects."""

from __future__ import annotations

from typing import Any


class MockToolSandbox:
    """Sandbox that records tool invocations without real I/O."""

    def __init__(self) -> None:
        self.refunds: list[dict[str, Any]] = []
        self.emails: list[dict[str, Any]] = []
        self.deletes: list[dict[str, Any]] = []
        self.lookups: list[dict[str, Any]] = []
        self._call_seq = 0

    def reset(self) -> None:
        self.refunds.clear()
        self.emails.clear()
        self.deletes.clear()
        self.lookups.clear()
        self._call_seq = 0

    def next_call_id(self) -> str:
        self._call_seq += 1
        return f"demo-tc-{self._call_seq}"

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "issue_refund":
            return self._issue_refund(arguments)
        if name == "send_email":
            return self._send_email(arguments)
        if name == "delete_account":
            return self._delete_account(arguments)
        if name == "lookup_order":
            return self._lookup_order(arguments)
        raise ValueError(f"unknown tool: {name}")

    def _issue_refund(self, arguments: dict[str, Any]) -> dict[str, Any]:
        record = {
            "order_id": arguments.get("order_id"),
            "amount": arguments.get("amount"),
            "approved": arguments.get("approved"),
        }
        self.refunds.append(record)
        return {
            "status": "ok",
            "mock": True,
            "refund_id": f"rfnd_{len(self.refunds)}",
            **record,
        }

    def _send_email(self, arguments: dict[str, Any]) -> dict[str, Any]:
        record = {
            "recipient": arguments.get("recipient"),
            "subject": arguments.get("subject"),
            "body": arguments.get("body"),
        }
        self.emails.append(record)
        return {
            "status": "ok",
            "mock": True,
            "delivered": False,
            "reason": "sandboxed_mock_no_delivery",
            **record,
        }

    def _delete_account(self, arguments: dict[str, Any]) -> dict[str, Any]:
        record = {
            "confirmed": arguments.get("confirmed"),
            "user_id": arguments.get("user_id"),
        }
        self.deletes.append(record)
        # Mock never actually deletes
        return {
            "status": "ok",
            "mock": True,
            "deleted": False,
            "reason": "sandboxed_mock_no_delete",
            **record,
        }

    def _lookup_order(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from demo_agent.context import DEMO_CONTEXT

        order_id = arguments.get("order_id")
        self.lookups.append({"order_id": order_id})
        for order in DEMO_CONTEXT["orders"]:
            if order["id"] == order_id:
                return {"status": "ok", "mock": True, "order": dict(order)}
        return {"status": "not_found", "mock": True, "order_id": order_id}
