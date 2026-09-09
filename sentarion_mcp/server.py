"""
Sentarion MCP — composite server upgrading Algernon + ArkHive + Humane.

Does NOT reimplement any upstream server. Connects to all three as an MCP
client and fuses them into one governed orchestration substrate:

  - Humane Intelligence — local covenant/identity gate (born-not-configured),
    zero-LLM governance, tamper-evident local chain.
  - ArkHive — hosted, tamper-evident audit/memory chain.
  - Algernon — fan-out planning/dispatch muscle.

What Sentarion adds that none of the three has alone:
  1. Cost prediction before dispatch (cost_estimate.py)
  2. Dependency-ordered fan-out/fan-in dispatch (dependency_graph.py)
  3. A TWO-CHAMBER governance gate (Humane + ArkHive, fail-closed) wrapping
     every orchestration call (govern_stub.py)
  4. Dual-chain memory: remember/recall/verify write and prove across BOTH
     the local Humane chain and the hosted ArkHive chain at once.
  5. Covenant-gated identity: sentarion_birth earns a soul_id before any
     governed action, honoring Humane's Law 5 (born, not configured).

Tools exposed:
  - sentarion_pro()
  - cost_estimate(k_tasks, input_price_per_mtok, output_price_per_mtok)
  - sentarion_birth(name, covenant)                 -> earn a soul_id (Humane)
  - remember(actor, action, data)                   -> dual-chain write
  - recall(actor, limit)                            -> merged dual-chain read
  - verify()                                        -> prove BOTH chains intact
  - govern(action, flags, rules)                    -> two-chamber verdict
  - orchestrate_and_record(goal, k, flags)          -> govern-gated plan+dispatch, auto-logged
  - dispatch_with_dependencies(tasks_json)          -> GOVERNED wave-ordered dispatch
  - recall_and_replan(query, k)                     -> history-primed Algernon plan
  - worktree(action, repo_path, ...)                -> governed git-worktree sandbox

Safety note (rogue-incident, 2026-08-19): every tool that EXECUTES work or
MUTATES state — orchestrate_and_record, dispatch_with_dependencies, and
worktree create/remove — passes the two-chamber fail-closed gate BEFORE any
effect. recall_and_replan is plan-only (no dispatch). The `worktree` skill
exists so orchestrated work runs in an isolated checkout, never live files.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import __version__
from .clients import (
    HumaneNotConfigured,
    algernon_session,
    arkhive_session,
    humane_session,
    record_ts,
    tool_json,
    tool_records,
    tool_text,
)
from .cost_estimate import estimate_dispatch_cost
from .dependency_graph import resolve_waves, fill_placeholders
from .doctor import run_doctor
from .quickstart import EXAMPLES as QUICKSTART_EXAMPLES, quickstart
from .govern_stub import govern_stub
from . import worktree as wt

def _exc_name(e: BaseException) -> str:
    """Return the underlying exception class name, unwrapping ExceptionGroup-like containers."""
    try:
        while getattr(e, "exceptions", None):
            e = e.exceptions[0]
    except Exception:
        pass
    return type(e).__name__



def _register_for_v2(email: str | None, product: str) -> dict:
    """Opt-in: request a 14-day v2 trial key. Sends ONLY the email the user typed. No email, nothing sent."""
    info = {
        "free_tier": "everything you use today stays free and open (Apache-2.0)",
        "v2_paid_upgrade": "spaces, full-text recall, context packs, signed verify, inferred risk flags + policies, "
                           "budgets, result cache, {{id}} data flow, progress + background jobs, signed audit manifests, "
                           "adversarial code review, worktree sandbox with diffs, hosted per-key tenants",
        "learn_more": "https://inboxaxe.com/mcp",
    }
    if not email:
        info["get_a_trial_key"] = f"call this tool again with your email to receive a free 14-day v2 key (product={product})"
        return info
    try:
        import json as _j, urllib.request as _u
        req = _u.Request("https://inboxaxe.com/api/v2/mcp/trial", method="POST",
                         data=_j.dumps({"email": email, "product": product, "source": f"{product} upgrade tool"}).encode(),
                         headers={"Content-Type": "application/json"})
        with _u.urlopen(req, timeout=10) as r:
            info["trial"] = _j.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        info["trial"] = {"error": f"could not reach inboxaxe.com ({type(e).__name__}) — email sam@inboxaxe.com for a key"}
    return info

INSTRUCTIONS = (
    "Sentarion gives your AI agents rules, memory, and receipts: a governed, fail-closed "
    "orchestration layer over Algernon (dispatch), ArkHive (hosted tamper-evident memory) and a "
    "local covenant chamber.\n\n"
    "Start by calling sentarion_birth once to obtain a soul_id, and pass that soul_id as the "
    "actor argument on every later call.\n\n"
    "Call govern before any action that sends, deletes, spends, deploys or edits files. A block "
    "verdict is final: do not retry it under another name and do not work around it.\n\n"
    "Never invent tool results, chain records or capabilities. If a chain reports not_configured "
    "or error, say so to the user instead of filling in what it might have said.\n\n"
    "dispatch_with_dependencies takes tasks_json, a JSON array of objects with id, prompt and "
    "depends_on (a list of ids). Tasks run in waves ordered by depends_on, and the text {{id}} "
    "inside a prompt is replaced with the result of the task with that id.\n\n"
    "Everything in this server is free and Apache-2.0; sentarion_pro describes the paid v2 "
    "control plane and never changes free behavior."
)

app = Server("sentarion-mcp", version=__version__, instructions=INSTRUCTIONS)


def _ok(payload) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _summarize_results(plan_and_results) -> dict:
    """tasks/succeeded/failed from an Algernon result when it carries a list of task dicts; else zeros."""
    items = plan_and_results.get("results") if isinstance(plan_and_results, dict) else None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return {"tasks": 0, "succeeded": 0, "failed": 0}
    failed = sum(1 for i in items if i.get("error") or i.get("result") is None)
    return {"tasks": len(items), "succeeded": len(items) - failed, "failed": failed}


V2_WOULD_ADD = ["signed run manifest", "typed retries", "SHA-bound verification evidence", "adversarial review gate"]

_PRO_TOPICS: dict[str, dict] = {
    "worktree": {
        "you_are_using": "The free worktree tool creates, lists and removes governed git worktrees so dispatched work never touches your live checkout.",
        "v2_adds": [
            "diff of a worktree against its base branch",
            "apply_patch into a worktree from a reviewed patch",
            "commit from a worktree with a signed manifest entry",
            "cleanup policies for stale worktrees",
        ],
    },
    "dispatch": {
        "you_are_using": "dispatch_with_dependencies runs tasks in waves ordered by depends_on and substitutes {{id}} results into dependent prompts.",
        "v2_adds": [
            "per-run budgets that stop dispatch before overspend",
            "a result cache so repeated prompts are not re-run",
            "typed retries with backoff for failed tasks",
            "MCP progress notifications and background jobs for long runs",
        ],
    },
    "govern": {
        "you_are_using": "govern asks two chambers (the local covenant chamber and hosted ArkHive) with zero LLM calls and fails closed.",
        "v2_adds": [
            "inferred risk flags (PII, credentials, money, irreversible, outbound, bulk) without hand-written flags",
            "stored, versioned policies per team",
            "a REVIEW verdict that waits for a single human yes",
            "concurrent chamber calls instead of sequential ones",
        ],
    },
    "memory": {
        "you_are_using": "remember, recall and verify write to and prove both chains: the local chamber and hosted ArkHive.",
        "v2_adds": [
            "full-text recall across records",
            "spaces that keep projects and tenants apart",
            "context packs that bundle prior runs into a new plan",
            "signed verify with a downloadable proof",
        ],
    },
    "review": {
        "you_are_using": "The free tier has no built-in code review; you can dispatch reviewers as ordinary tasks with dispatch_with_dependencies.",
        "v2_adds": [
            "adversarial multi-agent code review with finders per dimension",
            "skeptic agents that try to refute each finding",
            "a review gate that blocks a merge on unrefuted findings",
            "review evidence bound to commit SHAs",
        ],
    },
    "jobs": {
        "you_are_using": "Every free tool call runs inside one MCP request and returns when the work is done.",
        "v2_adds": [
            "background jobs that outlive a single tool call",
            "MCP progress notifications while a run executes",
            "job status and cancel tools",
            "no 120 second tool-call deaths on long runs",
        ],
    },
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="sentarion_doctor",
            description="Check that everything Sentarion needs is present and reachable (git, Algernon, local chamber, hosted ArkHive, fleet provider, Ollama, API key) and say exactly what to fix. Read-only; never prints secrets.",
            inputSchema={"type": "object", "properties": {"timeout_s": {"type": "number", "default": 3}}, "required": []},
        ),
        Tool(
            name="sentarion_quickstart",
            description="Canonical, runnable examples for every Sentarion capability: plan a feature, fan out research, dispatch with dependencies, use a worktree, remember a result, replan from memory.",
            inputSchema={"type": "object", "properties": {"topic": {"type": "string", "enum": list(QUICKSTART_EXAMPLES)}}, "required": []},
        ),
        Tool(
            name="sentarion_pro",
            description="Sentarion v2 — the paid upgrade: in-process (no per-call subprocesses), concurrent two-chamber gate with inferred risk flags + stored policies, {{id}} data-flow dispatch, signed audit manifests, adversarial multi-agent code review, worktree sandbox with diffs, real cost estimates, progress + background jobs. Free 0.x stays whole. Details + trial key: https://inboxaxe.com/mcp",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "optional — supply it to receive a free 14-day v2 trial key"},
                    "topic": {"type": "string", "enum": list(_PRO_TOPICS), "description": "optional — what v2 adds to the capability you are using right now"},
                },
                "required": [],
            },
        ),
        Tool(
            name="cost_estimate",
            description="Predict token cost of an Algernon fan-out BEFORE dispatching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "k_tasks": {"type": "integer"},
                    "input_price_per_mtok": {"type": "number"},
                    "output_price_per_mtok": {"type": "number"},
                },
                "required": ["k_tasks", "input_price_per_mtok", "output_price_per_mtok"],
            },
        ),
        Tool(
            name="sentarion_birth",
            description="Earn an identity (Humane Law 5: born, not configured) before acting. Returns a soul_id to use as `actor`.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "covenant": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "covenant"],
            },
        ),
        Tool(
            name="remember",
            description="Write a tamper-evident record to BOTH chains at once (local Humane + hosted ArkHive). Requires a born soul_id as actor.",
            inputSchema={
                "type": "object",
                "properties": {
                    "actor": {"type": "string"},
                    "action": {"type": "string"},
                    "data": {"type": "object"},
                },
                "required": ["actor", "action"],
            },
        ),
        Tool(
            name="recall",
            description="Read prior context from BOTH chains and merge it, newest first, so the AI need not re-derive it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "actor": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        ),
        Tool(
            name="verify",
            description="Prove BOTH audit chains (local Humane + hosted ArkHive) are unbroken.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="govern",
            description="Ask the two-chamber gate (Humane + ArkHive) 'may I?' before acting. Rule-based, zero-LLM, fail-closed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "flags": {"type": "array", "items": {"type": "string"}},
                    "rules": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="orchestrate_and_record",
            description="Two-chamber-govern-gated plan+dispatch via Algernon, auto-logged to both chains.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "k": {"type": "integer"},
                    "flags": {"type": "array", "items": {"type": "string"}},
                    "actor": {"type": "string"},
                },
                "required": ["goal", "k"],
            },
        ),
        Tool(
            name="dispatch_with_dependencies",
            description="Run tasks in dependency-ordered waves via Algernon (fan-out/fan-in).",
            inputSchema={
                "type": "object",
                "properties": {
                    "tasks_json": {
                        "type": "string",
                        "description": 'JSON array of {id, prompt, depends_on: [ids]}',
                    }
                },
                "required": ["tasks_json"],
            },
        ),
        Tool(
            name="recall_and_replan",
            description="Recall prior state from both chains, feed it into a new Algernon plan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer"},
                },
                "required": ["query", "k"],
            },
        ),
        Tool(
            name="worktree",
            description="Git-worktree sandbox skill: run dispatched work in an isolated worktree so it never touches the live checkout. action=create|list|remove. create/remove are two-chamber-governed; list is read-only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "list", "remove"]},
                    "repo_path": {"type": "string", "description": "path to the git repo"},
                    "branch": {"type": "string", "description": "create: new branch name"},
                    "base": {"type": "string", "description": "create: base ref (default HEAD)"},
                    "path": {"type": "string", "description": "create: explicit worktree dir (optional)"},
                    "worktree_path": {"type": "string", "description": "remove: worktree dir to remove"},
                    "force": {"type": "boolean", "description": "remove: allow uncommitted changes"},
                    "delete_branch": {"type": "string", "description": "remove: also delete this branch"},
                },
                "required": ["action", "repo_path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "sentarion_doctor":
        return _ok(await run_doctor(float(arguments.get("timeout_s", 3.0))))

    if name == "sentarion_quickstart":
        return _ok(quickstart(arguments.get("topic")))

    if name == "sentarion_pro":
        if arguments.get("email"):
            return _ok(_register_for_v2(arguments["email"], "sentarion-mcp"))
        topic = arguments.get("topic")
        if topic:
            info = _PRO_TOPICS.get(str(topic))
            if info is None:
                return _ok({"error": "unknown topic", "topics": list(_PRO_TOPICS)})
            return _ok({
                "you_are_using": info["you_are_using"],
                "v2_adds": list(info["v2_adds"]),
                "run": "sentarion_pro(email=...) for a trial key",
                "free_stays_free": True,
            })
        return _ok({
            "free_tier": "everything you are using right now — no limits removed, Apache-2.0 forever",
            "v2_paid_upgrade": {
                "what": [
                    "in-process ArkHive + Algernon (no subprocess + handshake per call)",
                    "concurrent two-chamber gate; inferred risk flags (PII, credentials, money, irreversible, outbound, bulk); stored, versioned policies; REVIEW verdict with a single human yes",
                    "dispatch with {{id}} data flow between tasks, budgets, result cache, retries",
                    "every run recorded as a signed manifest (prompt/result hashes, usage, cost)",
                    "adversarial multi-agent code review (finders per dimension, skeptics refute)",
                    "git-worktree sandbox: create / diff / apply_patch / commit — fleet edits never touch your checkout",
                    "MCP progress + background jobs — no more 120 s tool-call deaths",
                    "hosted endpoint with per-key tenant spaces",
                ],
                "get_a_trial_key": "https://inboxaxe.com/mcp",
            },
            "business_suite": "InboxAxe — your whole business inbox run by a governed RI: https://inboxaxe.com",
            "donate": "https://dondatabrain.com",
        })

    if name == "cost_estimate":
        return _ok(estimate_dispatch_cost(
            arguments["k_tasks"],
            arguments["input_price_per_mtok"],
            arguments["output_price_per_mtok"],
        ))

    if name == "sentarion_birth":
        payload = {"name": arguments["name"], "covenant": arguments["covenant"]}
        try:
            async with humane_session() as humane:
                result = await humane.call_tool("birth", payload)
            return _ok({"chain": "humane", "result": tool_json(result)})
        except HumaneNotConfigured:
            # Fall back to ArkHive birth if the hosted chain implements it. The hosted 0.x server
            # types `covenant` as a string; retry with a joined string if the list is rejected.
            async with arkhive_session() as arkhive:
                result = await arkhive.call_tool("birth", payload)
                if tool_text(result).startswith("Error executing tool"):
                    result = await arkhive.call_tool(
                        "birth", {"name": payload["name"], "covenant": "; ".join(payload["covenant"])}
                    )
            return _ok({"chain": "arkhive", "result": tool_json(result)})

    if name == "remember":
        payload = {
            "actor": arguments["actor"],
            "action": arguments.get("action", ""),
            "data": arguments.get("data", {}),
        }
        out = {}
        try:
            async with humane_session() as humane:
                r = await humane.call_tool("remember", payload)
            out["humane"] = tool_json(r)
        except HumaneNotConfigured:
            out["humane"] = "not_configured"
        except Exception as e:
            out["humane"] = f"error: {_exc_name(e)}"
        try:
            async with arkhive_session() as arkhive:
                r = await arkhive.call_tool("remember", payload)
            out["arkhive"] = tool_json(r)
        except Exception as e:
            out["arkhive"] = f"error: {_exc_name(e)}"
        return _ok({"written": out})

    if name == "recall":
        args = {"limit": arguments.get("limit", 10)}
        if arguments.get("actor"):
            args["actor"] = arguments["actor"]
        merged = []
        try:
            async with humane_session() as humane:
                r = await humane.call_tool("recall", args)
            merged += [{**x, "_chain": "humane"} for x in tool_records(r)]
        except HumaneNotConfigured:
            pass
        except Exception:
            pass
        try:
            async with arkhive_session() as arkhive:
                r = await arkhive.call_tool("recall", args)
            merged += [{**x, "_chain": "arkhive"} for x in tool_records(r)]
        except Exception:
            pass
        merged.sort(key=record_ts, reverse=True)
        return _ok(merged[: arguments.get("limit", 10)])

    if name == "verify":
        out = {}
        try:
            async with humane_session() as humane:
                r = await humane.call_tool("verify", {})
            out["humane"] = tool_json(r)
        except HumaneNotConfigured:
            out["humane"] = "not_configured"
        except Exception as e:
            out["humane"] = f"error: {_exc_name(e)}"
        try:
            async with arkhive_session() as arkhive:
                r = await arkhive.call_tool("verify", {})
            out["arkhive"] = tool_json(r)
        except Exception as e:
            out["arkhive"] = f"error: {_exc_name(e)}"
        return _ok({"chains": out})

    if name == "govern":
        decision = await govern_stub(
            arguments["action"],
            {"flags": arguments.get("flags"), "rules": arguments.get("rules")},
        )
        return _ok(decision)

    if name == "orchestrate_and_record":
        goal, k = arguments["goal"], arguments["k"]
        actor = arguments.get("actor", "sentarion")
        run = {
            "run_id": uuid.uuid4().hex,
            "goal": goal,
            "k": k,
            "actor": actor,
            "started_at": _utcnow(),
            "finished_at": None,
        }

        decision = await govern_stub(
            "orchestrate", {"goal": goal, "k": k, "flags": arguments.get("flags")}
        )
        if decision["decision"] != "approve":
            run["finished_at"] = _utcnow()
            return _ok({"run": run, "governance": decision, "dispatched": False})

        async with algernon_session() as algernon:
            r = await algernon.call_tool("algernon_orchestrate", {"goal": goal, "k": k})
        plan_and_results = tool_json(r)
        summary = _summarize_results(plan_and_results)

        record = {
            "actor": actor,
            "action": "orchestrate",
            "data": {"run_id": run["run_id"], "goal": goal, "k": k, "summary": summary, "results": plan_and_results},
        }
        memory: dict[str, str] = {}
        try:
            async with arkhive_session() as arkhive:
                await arkhive.call_tool("remember", record)
            memory["arkhive"] = "recorded"
        except Exception as e:  # noqa: BLE001
            memory["arkhive"] = f"error: {_exc_name(e)}"
        try:
            async with humane_session() as humane:
                await humane.call_tool("remember", record)
            memory["humane"] = "recorded"
        except HumaneNotConfigured:
            memory["humane"] = "not_configured"
        except Exception as e:  # noqa: BLE001
            memory["humane"] = f"error: {_exc_name(e)}"

        run["finished_at"] = _utcnow()
        return _ok({
            "run": run,
            "governance": decision,
            "results": plan_and_results,
            "summary": summary,
            "memory": memory,
            "v2_would_add": list(V2_WOULD_ADD),
        })

    if name == "dispatch_with_dependencies":
        tasks = json.loads(arguments["tasks_json"])
        try:
            waves = resolve_waves(tasks)
        except ValueError as e:
            return _ok({"error": str(e), "dispatched": False})

        # SAFETY GATE (rogue-incident root cause, 2026-08-19): dispatch runs
        # Algernon worker waves that can edit files. It MUST pass the
        # two-chamber gate before any wave executes. Flags mark it as an
        # effecting, file-touching action so covenant rules can veto it.
        decision = await govern_stub(
            "dispatch_with_dependencies",
            {
                "flags": ["executes_tasks", "may_edit_files"]
                + list(arguments.get("flags") or []),
                "rules": arguments.get("rules"),
            },
        )
        if decision["decision"] != "approve":
            return _ok({"governance": decision, "dispatched": False})

        all_results = []
        completed: dict[str, str] = {}
        async with algernon_session() as algernon:
            for wave in waves:
                wave_payload = [{"id": t["id"], "prompt": fill_placeholders(t["prompt"], completed)} for t in wave]
                r = await algernon.call_tool(
                    "algernon_dispatch", {"tasks_json": json.dumps(wave_payload)}
                )
                parsed = tool_json(r)
                all_results.append(parsed)
                for item in (parsed.get("results") if isinstance(parsed, dict) else []) or []:
                    if isinstance(item, dict) and item.get("result") is not None:
                        completed[str(item.get("id"))] = str(item["result"])
        return _ok({"governance": decision, "waves": len(waves), "results": all_results,
                    "data_flow": "dependents received {{id}} substitutions from completed tasks"})

    if name == "recall_and_replan":
        query, k = arguments["query"], arguments["k"]
        history = None
        try:
            async with arkhive_session() as arkhive:
                r = await arkhive.call_tool("recall", {"limit": 10})
            history = tool_json(r)
        except Exception as e:
            history = f"(arkhive recall unavailable: {type(e).__name__})"

        async with algernon_session() as algernon:
            r = await algernon.call_tool(
                "algernon_plan",
                {"goal": f"{query}\n\nPrior context:\n{history}", "k": k},
            )
        return _ok(tool_json(r))

    if name == "worktree":
        action = arguments["action"]
        repo_path = arguments["repo_path"]
        try:
            if action == "list":
                return _ok({"worktrees": wt.list_worktrees(repo_path)})

            if action == "create":
                if not arguments.get("branch"):
                    return _ok({"error": "create requires `branch`"})
                decision = await govern_stub(
                    "worktree_create",
                    {"flags": ["mutates_repo", "creates_branch"],
                     "rules": arguments.get("rules")},
                )
                if decision["decision"] != "approve":
                    return _ok({"governance": decision, "created": False})
                result = wt.create(
                    repo_path,
                    arguments["branch"],
                    base=arguments.get("base"),
                    path=arguments.get("path"),
                )
                return _ok({"governance": decision, **result})

            if action == "remove":
                if not arguments.get("worktree_path"):
                    return _ok({"error": "remove requires `worktree_path`"})
                decision = await govern_stub(
                    "worktree_remove",
                    {"flags": ["mutates_repo", "deletes_files"],
                     "rules": arguments.get("rules")},
                )
                if decision["decision"] != "approve":
                    return _ok({"governance": decision, "removed": False})
                result = wt.remove(
                    repo_path,
                    arguments["worktree_path"],
                    force=bool(arguments.get("force")),
                    delete_branch=arguments.get("delete_branch"),
                )
                return _ok({"governance": decision, **result})

            return _ok({"error": f"unknown worktree action: {action}"})
        except wt.GitError as e:
            return _ok({"error": f"git_error: {e}"})

    raise ValueError(f"Unknown tool: {name}")


async def _run():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def main():
    import asyncio

    asyncio.run(_run())


if __name__ == "__main__":
    main()
