"""
Fail-closed governance gate — two-chamber, upgraded 2026-08-19.

Two real governors, TWO DIFFERENT wire schemas (verified against the live
servers — do not re-guess them):

  Humane (local, zero-LLM rule engine — the authoritative rule gate):
    in : {"action": str, "flags": [str], "rules": [{"trigger": str, "action": str}]}
    out: {"vetoed": bool, "reason": ...}

  ArkHive (hosted audit chain; its govern endpoint cleanly supports the
  allowed/echo path, and is the tamper-evident mirror):
    in : {"action": str, "flags": {..}, "rules": {..}}   # dicts, not lists
    out: {"vetoed": bool, "reason": ..., "verdict": "ALLOWED"|...}

Verdicts are BINARY — vetoed or allowed. There is no "pending" state.

Decision rule:
  * A chamber that RENDERS a verdict of vetoed=True blocks, unilaterally.
  * A chamber that fails to render a verdict (transport error, impl error,
    unparseable shape) counts as NOT REACHED — it never manufactures a false
    veto that would jam the gate when the other chamber cleared the action.
  * If NO chamber renders any verdict, fail closed → block. An unreachable
    governor never silently approves.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from .clients import (
    HumaneNotConfigured,
    arkhive_session,
    humane_session,
    tool_json,
    tool_text,
)


class GovernDecision(TypedDict):
    decision: Literal["approve", "block"]
    reason: str
    chambers: dict


# Default veto rules for orchestration dispatch. Callers may extend via the
# `rules` argument; these minimums always apply. Canonical list form (Humane).
_BASE_RULES = [
    {"trigger": "no_consent", "action": "refuse"},
    {"trigger": "raw_pii", "action": "refuse"},
    {"trigger": "spam_burst", "action": "throttle"},
]


def _flags_dict(flags: list[str]) -> dict:
    """ArkHive wants flags as a {name: true} map."""
    return {f: True for f in flags}


def _rendered_verdict(result):
    """Interpret one governor's response.

    Returns (rendered: bool, vetoed: bool, reason: str).
      rendered=True  -> the governor actually decided (dict with 'vetoed').
      rendered=False -> the governor failed to decide (error / bad shape).
    """
    text = tool_text(result)
    if text.startswith("Error executing tool"):
        return False, False, text.splitlines()[0][:160]
    data = tool_json(result)
    if isinstance(data, dict) and "vetoed" in data:
        vetoed = bool(data["vetoed"])
        reason = str(data.get("reason") or ("vetoed" if vetoed else "allowed"))
        return True, vetoed, reason
    # Answered, but not a shape we recognize as a verdict.
    return False, False, "no_verdict_field"


async def _ask_humane(action, flags, rules):
    try:
        async with humane_session() as humane:
            result = await humane.call_tool(
                "govern", {"action": action, "flags": flags, "rules": rules}
            )
        return _rendered_verdict(result)
    except HumaneNotConfigured:
        return False, False, "humane_not_configured"
    except Exception as e:
        return False, False, f"humane_transport_error: {type(e).__name__}"


async def _ask_arkhive(action, flags):
    # ArkHive's hosted govern cleanly supports the flags-dict allowed/echo path;
    # rule enforcement is Humane's job, so we send an empty rules map here.
    try:
        async with arkhive_session() as arkhive:
            result = await arkhive.call_tool(
                "govern",
                {"action": action, "flags": _flags_dict(flags), "rules": {}},
            )
        return _rendered_verdict(result)
    except Exception as e:
        return False, False, f"arkhive_transport_error: {type(e).__name__}"


async def govern_stub(action: str, context: dict) -> GovernDecision:
    """Ask the two-chamber gate 'may I?' before acting.

    `context` may carry:
      flags: list[str] — condition flags (e.g. "no_consent", "raw_pii")
      rules: list[dict] — extra {trigger, action} veto rules (Humane form)
    """
    flags = list(context.get("flags") or [])
    rules = _BASE_RULES + list(context.get("rules") or [])

    h_rendered, h_vetoed, h_reason = await _ask_humane(action, flags, rules)
    a_rendered, a_vetoed, a_reason = await _ask_arkhive(action, flags)

    chambers = {
        "humane": {"rendered": h_rendered, "vetoed": h_vetoed, "reason": h_reason},
        "arkhive": {"rendered": a_rendered, "vetoed": a_vetoed, "reason": a_reason},
    }

    # Any chamber that actually rendered a veto blocks.
    if (h_rendered and h_vetoed) or (a_rendered and a_vetoed):
        who = "humane" if (h_rendered and h_vetoed) else "arkhive"
        return GovernDecision(
            decision="block", reason=chambers[who]["reason"], chambers=chambers
        )

    # No veto rendered. Require at least one chamber to have actually decided.
    if not (h_rendered or a_rendered):
        return GovernDecision(
            decision="block",
            reason="no_governor_rendered_a_verdict_fail_closed",
            chambers=chambers,
        )

    return GovernDecision(decision="approve", reason="allowed", chambers=chambers)
