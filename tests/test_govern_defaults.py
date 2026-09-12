"""The free gate must say NO to the obvious things without being told how.

Measured 2026-09-10 from a clean install: govern("delete the production database") -> approve, and even
govern(..., flags=["irreversible"]) -> approve, because the only default rules were no_consent / raw_pii /
spam_burst. A gate that approves deleting production is broken, not tiered. This is the regression net:
the obvious risk classes are inferred from the action text, carry default refuse rules, and block.
"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from mcp.types import TextContent

from sentarion_mcp import govern_stub as g


class Chamber:
    """The 0.2.1 chain's govern: a rule whose trigger is among the flags vetoes. Records what it was asked."""

    def __init__(self):
        self.asked = []

    async def call_tool(self, name, arguments):
        self.asked.append(arguments)
        flags = arguments.get("flags") or []
        flags = list(flags) if isinstance(flags, list) else [k for k, v in flags.items() if v]
        rules = arguments.get("rules") or []
        rules = rules if isinstance(rules, list) else [{"trigger": k, "action": v} for k, v in rules.items()]
        for r in rules:
            if r.get("trigger") in flags:
                text = '{"vetoed": true, "reason": "Veto: %s -> %s", "verdict": "VETOED"}' % (r["trigger"], r.get("action"))
                break
        else:
            text = '{"vetoed": false, "reason": "allowed", "verdict": "ALLOWED"}'
        return SimpleNamespace(content=[TextContent(type="text", text=text)])


def _gate(monkeypatch, humane=True, arkhive=True):
    h, a = Chamber(), Chamber()

    @asynccontextmanager
    async def humane_session():
        if not humane:
            raise g.HumaneNotConfigured("no local chamber")
        yield h

    @asynccontextmanager
    async def arkhive_session():
        if not arkhive:
            raise ConnectionError("hosted down")
        yield a

    monkeypatch.setattr(g, "humane_session", humane_session)
    monkeypatch.setattr(g, "arkhive_session", arkhive_session)
    return h, a


def _govern(action, **ctx):
    return asyncio.run(g.govern_stub(action, ctx))


def test_infer_flags_catches_the_obvious_and_leaves_ordinary_work_alone():
    assert "irreversible" in g.infer_flags("delete the production database")
    assert "irreversible" in g.infer_flags("rm -rf the deploy directory and force-push main")
    assert "external_send" in g.infer_flags("email all 4,000 customers a discount code")
    assert "financial" in g.infer_flags("pay the $1,200 invoice to the vendor")
    assert "external_send" in g.infer_flags("deploy the new build to production")
    for benign in ("write a summary file", "list three risks of storing session tokens in localStorage",
                   "compare token-bucket and sliding-window rate limiting", "draft the release notes"):
        assert g.infer_flags(benign) == [], benign


def test_dangerous_actions_block_by_default(monkeypatch):
    _gate(monkeypatch)
    for action, flag in (("delete the production database", "irreversible"),
                         ("email all 4,000 customers a discount code", "external_send"),
                         ("rm -rf the deploy directory and force-push main", "irreversible"),
                         ("charge the customer's card $500", "financial"),
                         ("deploy this to production now", "external_send")):
        d = _govern(action)
        assert d["decision"] == "block", action
        assert flag in d["inferred_flags"] and flag in d["reason"], action


def test_ordinary_work_is_approved_and_nothing_is_inferred(monkeypatch):
    h, a = _gate(monkeypatch)
    d = _govern("write a summary file")
    assert d["decision"] == "approve" and d["inferred_flags"] == [] and d["flags"] == []
    # both chambers were asked with the default rules, so either one can veto
    assert any(r["trigger"] == "irreversible" for r in h.asked[-1]["rules"])


def test_caller_flags_block_too_and_merge_with_inferred(monkeypatch):
    _gate(monkeypatch)
    d = _govern("archive last quarter's reports", flags=["irreversible"])
    assert d["decision"] == "block" and d["flags"] == ["irreversible"] and d["inferred_flags"] == []
    d = _govern("delete old reports", flags=["external_send"])
    assert d["decision"] == "block" and set(d["flags"]) == {"external_send", "irreversible"}


def test_the_hosted_chamber_alone_still_blocks(monkeypatch):
    """No local chamber (not configured): the hosted chamber gets the same default rules and vetoes."""
    _gate(monkeypatch, humane=False)
    d = _govern("drop the users table")
    assert d["decision"] == "block" and d["chambers"]["humane"]["rendered"] is False
    assert d["chambers"]["arkhive"]["vetoed"] is True


def test_no_chamber_at_all_fails_closed(monkeypatch):
    _gate(monkeypatch, humane=False, arkhive=False)
    d = _govern("write a summary file")
    assert d["decision"] == "block" and "fail_closed" in d["reason"]
