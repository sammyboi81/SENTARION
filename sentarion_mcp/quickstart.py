"""
sentarion_quickstart — canonical, runnable examples for every Sentarion capability.

Each example is a valid call for its tool (arguments satisfy the tool's inputSchema),
so a client can copy it verbatim. Replace "<soul_id from sentarion_birth>" with the
soul_id you were given at birth.
"""

from __future__ import annotations

import json

SOUL_ID_HINT = "<soul_id from sentarion_birth>"

EXAMPLES: dict[str, dict] = {
    "plan_a_feature": {
        "goal": "Plan a small feature and let three governed workers draft its parts in parallel.",
        "tool": "orchestrate_and_record",
        "arguments": {
            "goal": "Add password reset to a Flask app: token model, email template, reset endpoint. Return a short plan per part.",
            "k": 3,
            "actor": SOUL_ID_HINT,
        },
        "expect": "A run block with run_id and timing, the governance verdict, Algernon's plan and results, a tasks/succeeded/failed summary, and whether both memory chains recorded it.",
        "then": "Read summary and memory first; if memory.arkhive or memory.humane is not recorded, tell the user before relying on recall later.",
    },
    "fan_out_research": {
        "goal": "Fan out an open research question to several workers and collect their answers in one governed run.",
        "tool": "orchestrate_and_record",
        "arguments": {
            "goal": "Compare token-bucket, sliding-window and fixed-window rate limiting for a public HTTP API: one worker per approach, each returns pros, cons and a recommendation.",
            "k": 3,
            "actor": SOUL_ID_HINT,
        },
        "expect": "The same run shape as plan_a_feature, with one result per worker under results.",
        "then": "Call remember with the conclusion so recall_and_replan can build on it next time.",
    },
    "dispatch_dependencies": {
        "goal": "Run three tasks where the third depends on the first two and receives their results through {{id}} placeholders.",
        "tool": "dispatch_with_dependencies",
        "arguments": {
            "tasks_json": json.dumps(
                [
                    {"id": "t1", "prompt": "List three risks of storing session tokens in localStorage.", "depends_on": []},
                    {"id": "t2", "prompt": "List three risks of storing session tokens in cookies.", "depends_on": []},
                    {
                        "id": "t3",
                        "prompt": "Given these findings, recommend one approach and justify it in five sentences.\n\nlocalStorage risks:\n{{t1}}\n\nCookie risks:\n{{t2}}",
                        "depends_on": ["t1", "t2"],
                    },
                ]
            )
        },
        "expect": "governance, waves (2 here), results per wave, and a data_flow note confirming that {{t1}} and {{t2}} were substituted into t3.",
        "then": "Inspect results[1] for t3; if governance.decision is block, dispatched is false and nothing ran.",
    },
    "use_a_worktree": {
        "goal": "Give dispatched work an isolated git worktree so it never edits the live checkout.",
        "tool": "worktree",
        "arguments": {
            "action": "create",
            "repo_path": "<absolute path to your git repo>",
            "branch": "sentarion/scratch",
        },
        "expect": "governance plus worktree_path, branch and base; the worktree is a sibling directory of the repo.",
        "then": "Use an absolute repo_path because the server resolves relative paths in its own working directory. Point dispatched tasks at worktree_path; when done, call worktree with action remove and that worktree_path.",
    },
    "remember_result": {
        "goal": "Write a tamper-evident record of a result to both chains at once.",
        "tool": "remember",
        "arguments": {
            "actor": SOUL_ID_HINT,
            "action": "decision",
            "data": {"topic": "session storage", "decision": "httpOnly cookies", "why": "not readable by injected scripts"},
        },
        "expect": "written.humane and written.arkhive, each either the chain's own receipt, not_configured, or error: <type>.",
        "then": "If either chain says error, report it to the user; do not claim the record exists on that chain.",
    },
    "replan_from_memory": {
        "goal": "Pull prior records from both chains and let Algernon plan the next step on top of them (plan only, nothing runs).",
        "tool": "recall_and_replan",
        "arguments": {"query": "Continue the session storage work: what should we build next?", "k": 3},
        "expect": "Algernon's plan primed with the recalled history; no tasks are dispatched.",
        "then": "Hand the plan to orchestrate_and_record or dispatch_with_dependencies to execute it under governance.",
    },
}

TOPICS: list[str] = list(EXAMPLES)


def quickstart(topic: str | None = None) -> dict:
    """No topic: the start-here order plus every example. A topic: that example, or an error dict."""
    if topic is None or topic == "":
        return {"start_here": ["sentarion_doctor", "sentarion_birth"], "examples": EXAMPLES}
    example = EXAMPLES.get(str(topic))
    if example is None:
        return {"error": "unknown topic", "topics": TOPICS}
    return {"example": example}
