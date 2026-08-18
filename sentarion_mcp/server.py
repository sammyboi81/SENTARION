"""
Sentarion MCP — composite server wrapping Algernon + ArkHive.

Does NOT reimplement either upstream server. Connects to both as an MCP
client and adds three things neither has on its own:
  1. Cost prediction before dispatch (cost_estimate.py)
  2. Dependency-ordered fan-out/fan-in dispatch (dependency_graph.py)
  3. A governance gate + auto-audit-log wrapper around Algernon calls
     (govern_stub.py — SEE THAT FILE, it is a placeholder pending the
     real ArkHive `govern` schema)

Tools exposed:
  - cost_estimate(goal, k, input_price_per_mtok, output_price_per_mtok)
  - orchestrate_and_record(goal, k)   -> govern-gated plan+dispatch, auto-remembered
  - dispatch_with_dependencies(tasks_json)  -> wave-ordered dispatch via Algernon
  - recall_and_replan(query, k)       -> pull ArkHive history into a new Algernon plan
"""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .clients import algernon_session, arkhive_session
from .cost_estimate import estimate_dispatch_cost
from .dependency_graph import resolve_waves
from .govern_stub import govern_stub  # real ArkHive govern client, fail-closed

app = Server("sentarion-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
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
            name="orchestrate_and_record",
            description="Govern-gated plan+dispatch via Algernon, auto-logged to ArkHive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "k": {"type": "integer"},
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
            description="Recall prior ArkHive state on a topic, feed it into a new Algernon plan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer"},
                },
                "required": ["query", "k"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "cost_estimate":
        result = estimate_dispatch_cost(
            arguments["k_tasks"],
            arguments["input_price_per_mtok"],
            arguments["output_price_per_mtok"],
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "orchestrate_and_record":
        goal, k = arguments["goal"], arguments["k"]

        decision = await govern_stub("orchestrate", {"goal": goal, "k": k})
        if decision["decision"] != "approve":
            return [TextContent(type="text", text=json.dumps(decision, indent=2))]

        async with algernon_session() as algernon:
            plan_and_results = await algernon.call_tool(
                "algernon_orchestrate", {"goal": goal, "k": k}
            )

        async with arkhive_session() as arkhive:
            await arkhive.call_tool(
                "remember",
                {"content": json.dumps(plan_and_results), "tags": ["orchestrate", goal[:64]]},
            )

        return [TextContent(type="text", text=json.dumps(plan_and_results, indent=2))]

    if name == "dispatch_with_dependencies":
        tasks = json.loads(arguments["tasks_json"])
        waves = resolve_waves(tasks)

        all_results = []
        async with algernon_session() as algernon:
            for wave in waves:
                wave_payload = [{"id": t["id"], "prompt": t["prompt"]} for t in wave]
                wave_result = await algernon.call_tool(
                    "algernon_dispatch", {"tasks_json": json.dumps(wave_payload)}
                )
                all_results.append(wave_result)

        return [TextContent(type="text", text=json.dumps(all_results, indent=2))]

    if name == "recall_and_replan":
        query, k = arguments["query"], arguments["k"]

        async with arkhive_session() as arkhive:
            history = await arkhive.call_tool("recall", {"query": query})

        async with algernon_session() as algernon:
            plan = await algernon.call_tool(
                "algernon_plan",
                {"goal": f"{query}\n\nPrior context:\n{history}", "k": k},
            )

        return [TextContent(type="text", text=json.dumps(plan, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def _run():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def main():
    import asyncio

    asyncio.run(_run())


if __name__ == "__main__":
    main()
