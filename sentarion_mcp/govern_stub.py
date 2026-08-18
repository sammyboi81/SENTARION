"""
Real ArkHive `govern` client — stub replaced 2026-08-18.

Verified against the live engine (GovernanceBlock in senthar_runtime.py,
exposed by ArkHive/CSI MCP servers). The REAL interface, confirmed from
source — do not re-guess it:

    wire in : {"action": str (required), "flags": [str], "rules": [{"trigger": str, "action": str}]}
    wire out: {"action": ..., "vetoed": bool, "reason": "allowed" | str,
               "engine": "zero-LLM rule gate", "auditable": true}

Verdicts are BINARY — vetoed or allowed. There is no "pending" state in the
engine; this module keeps "pending" out of its vocabulary on purpose.
Fail-closed: if ArkHive can't be reached or returns an unparseable shape,
the decision is "block" — an unreachable governor never silently approves.
"""

from __future__ import annotations

import json
from typing import Literal, TypedDict

from .clients import arkhive_session


class GovernDecision(TypedDict):
    decision: Literal["approve", "block"]
    reason: str


# Default veto rules for orchestration dispatch. Callers may extend via the
# `rules` argument; these minimums always apply.
_BASE_RULES = [
    {"trigger": "no_consent", "action": "refuse"},
    {"trigger": "raw_pii", "action": "refuse"},
    {"trigger": "spam_burst", "action": "throttle"},
]


async def govern_stub(action: str, context: dict) -> GovernDecision:
    """Ask ArkHive's zero-LLM rule gate 'may I?' before dispatching.

    `context` may carry:
      flags: list[str] — condition flags (e.g. "contains_pii", "financial")
      rules: list[dict] — extra {trigger, action} veto rules for this call
    Anything else in context is informational and not sent over the wire.
    """
    flags = list(context.get("flags") or [])
    rules = _BASE_RULES + list(context.get("rules") or [])

    try:
        async with arkhive_session() as arkhive:
            result = await arkhive.call_tool(
                "govern", {"action": action, "flags": flags, "rules": rules}
            )
        # MCP tool results arrive as content blocks; the gate returns JSON text.
        raw = ""
        for block in getattr(result, "content", []) or []:
            if getattr(block, "type", "") == "text":
                raw += block.text
        data = json.loads(raw)
        vetoed = bool(data.get("vetoed"))
        reason = str(data.get("reason") or ("vetoed" if vetoed else "allowed"))
        return GovernDecision(
            decision="block" if vetoed else "approve", reason=reason
        )
    except Exception as e:  # unreachable/malformed governor -> FAIL CLOSED
        return GovernDecision(
            decision="block",
            reason=f"governor_unreachable_fail_closed: {type(e).__name__}",
        )
