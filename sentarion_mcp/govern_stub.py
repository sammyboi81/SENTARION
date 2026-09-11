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

import re
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
    flags: list
    inferred_flags: list


# Default veto rules for orchestration dispatch. Callers may extend via the
# `rules` argument; these minimums always apply. Canonical list form (Humane).
_BASE_RULES = [
    {"trigger": "no_consent", "action": "refuse"},
    {"trigger": "raw_pii", "action": "refuse"},
    {"trigger": "spam_burst", "action": "throttle"},
    # The obvious risk classes refuse by default. Measured 2026-09-10 from a clean install: without these,
    # govern("delete the production database") - and even the same call with flags=["irreversible"] - was
    # APPROVED, because no rule named those triggers. A gate that says yes to that is broken, not tiered.
    {"trigger": "irreversible", "action": "refuse"},
    {"trigger": "external_send", "action": "refuse"},
    {"trigger": "spends_money", "action": "refuse"},
    {"trigger": "deploys", "action": "refuse"},
]

# What the free gate infers from the action text by itself: the verbs anyone would call dangerous. Deliberately
# small and literal (v2 goes further: PII, credentials, bulk scope, stored policies, and a REVIEW verdict a human
# can turn into a yes). Word-boundary matches, case-insensitive; ordinary planning text matches nothing.
_INFER = {
    "irreversible": re.compile(
        r"\b(delete|drop|destroy|wipe|purge|truncate|erase|obliterate)\b|\brm\s+-[a-z]*r[a-z]*f|\bforce[- ]push|"
        r"\breset\s+--hard|\bshred\b", re.I),
    "external_send": re.compile(
        r"\b(email|e-mail|send|post|publish|tweet|broadcast|dm|text|message|notify)\b[^.]{0,60}\b(all|every|everyone|"
        r"customers?|subscribers?|users|list|contacts|followers|public|external)\b", re.I),
    "spends_money": re.compile(r"\b(pay|charge|transfer|wire|refund|purchase|buy|bill)\b|\$\s?\d", re.I),
    "deploys": re.compile(r"\b(deploy|release|ship|roll\s?out|push)\b[^.]{0,40}\b(prod|production|live|staging|main)\b", re.I),
}


def infer_flags(action: str) -> list[str]:
    """Risk flags the free gate reads off the action text itself (see _INFER). Returns a sorted list."""
    text = action or ""
    return sorted(flag for flag, rx in _INFER.items() if rx.search(text))


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


async def _ask_arkhive(action, flags, rules):
    # ArkHive's hosted govern takes flags as a {name: true} map and rules as a {trigger: action} map (its
    # _as_rules accepts both forms). It gets the SAME rules as the local chamber, so when the local chamber is
    # not configured the hosted one still vetoes the dangerous classes instead of echoing "allowed".
    try:
        async with arkhive_session() as arkhive:
            result = await arkhive.call_tool(
                "govern",
                {"action": action, "flags": _flags_dict(flags),
                 "rules": {r["trigger"]: r.get("action", "refuse") for r in rules if r.get("trigger")}},
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
    given = list(context.get("flags") or [])
    inferred = infer_flags(action)
    flags = sorted(set(given) | set(inferred))
    rules = _BASE_RULES + list(context.get("rules") or [])

    h_rendered, h_vetoed, h_reason = await _ask_humane(action, flags, rules)
    a_rendered, a_vetoed, a_reason = await _ask_arkhive(action, flags, rules)

    chambers = {
        "humane": {"rendered": h_rendered, "vetoed": h_vetoed, "reason": h_reason},
        "arkhive": {"rendered": a_rendered, "vetoed": a_vetoed, "reason": a_reason},
    }

    # Any chamber that actually rendered a veto blocks.
    if (h_rendered and h_vetoed) or (a_rendered and a_vetoed):
        who = "humane" if (h_rendered and h_vetoed) else "arkhive"
        return GovernDecision(
            decision="block", reason=chambers[who]["reason"], chambers=chambers, flags=flags, inferred_flags=inferred
        )

    # No veto rendered. Require at least one chamber to have actually decided.
    if not (h_rendered or a_rendered):
        return GovernDecision(
            decision="block",
            reason="no_governor_rendered_a_verdict_fail_closed",
            chambers=chambers, flags=flags, inferred_flags=inferred,
        )

    return GovernDecision(decision="approve", reason="allowed", chambers=chambers, flags=flags, inferred_flags=inferred)
