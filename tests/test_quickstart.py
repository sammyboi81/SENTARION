"""WO-S3: every quickstart example is a valid call for a registered tool."""

import asyncio
import json

from sentarion_mcp import quickstart as qs
from sentarion_mcp import server
from sentarion_mcp.clients import tool_json

EXPECTED_TOPICS = {
    "plan_a_feature",
    "fan_out_research",
    "dispatch_dependencies",
    "use_a_worktree",
    "remember_result",
    "replan_from_memory",
}
FIELDS = ("goal", "tool", "arguments", "expect", "then")


def _tools_by_name() -> dict:
    return {t.name: t for t in asyncio.run(server.list_tools())}


def test_examples_keys_exact():
    assert set(qs.EXAMPLES) == EXPECTED_TOPICS


def test_every_example_has_five_fields_and_is_json_serializable():
    for topic, ex in qs.EXAMPLES.items():
        assert set(ex) == set(FIELDS), topic
        for f in ("goal", "tool", "expect", "then"):
            assert isinstance(ex[f], str) and ex[f].strip(), (topic, f)
            assert "!" not in ex[f], (topic, f)
        assert isinstance(ex["arguments"], dict), topic
        json.dumps(ex["arguments"])


def test_every_example_targets_a_registered_tool_and_meets_required():
    tools = _tools_by_name()
    for topic, ex in qs.EXAMPLES.items():
        assert ex["tool"] in tools, (topic, ex["tool"])
        schema = tools[ex["tool"]].inputSchema
        for req in schema.get("required", []):
            assert req in ex["arguments"], (topic, req)
        for key in ex["arguments"]:
            assert key in schema["properties"], (topic, key)


def test_dispatch_example_carries_placeholders():
    ex = qs.EXAMPLES["dispatch_dependencies"]
    tasks = json.loads(ex["arguments"]["tasks_json"])
    t3 = next(t for t in tasks if t["id"] == "t3")
    assert set(t3["depends_on"]) == {"t1", "t2"}
    assert "{{t1}}" in t3["prompt"] and "{{t2}}" in t3["prompt"]


def test_quickstart_no_topic_shape():
    out = qs.quickstart(None)
    assert out["start_here"] == ["sentarion_doctor", "sentarion_birth"]
    assert set(out["examples"]) == EXPECTED_TOPICS


def test_quickstart_bogus_topic_shape():
    out = qs.quickstart("bogus")
    assert out == {"error": "unknown topic", "topics": list(qs.EXAMPLES)}


def test_quickstart_known_topic():
    out = qs.quickstart("use_a_worktree")
    assert out == {"example": qs.EXAMPLES["use_a_worktree"]}


def test_tool_registered_and_returns_six_examples():
    tools = _tools_by_name()
    assert "sentarion_quickstart" in tools
    assert set(tools["sentarion_quickstart"].inputSchema["properties"]["topic"]["enum"]) == EXPECTED_TOPICS
    out = tool_json(_Result(asyncio.run(server.call_tool("sentarion_quickstart", {}))))
    assert len(out["examples"]) == 6
    bogus = tool_json(_Result(asyncio.run(server.call_tool("sentarion_quickstart", {"topic": "bogus"}))))
    assert bogus["error"] == "unknown topic"


def test_sentarion_pro_topic_and_default():
    tools = _tools_by_name()
    props = tools["sentarion_pro"].inputSchema["properties"]
    assert set(props["topic"]["enum"]) == {"worktree", "dispatch", "govern", "memory", "review", "jobs"}
    for topic in props["topic"]["enum"]:
        out = tool_json(_Result(asyncio.run(server.call_tool("sentarion_pro", {"topic": topic}))))
        assert set(out) == {"you_are_using", "v2_adds", "run", "free_stays_free"}, topic
        assert 3 <= len(out["v2_adds"]) <= 5, topic
        assert out["free_stays_free"] is True
        assert out["run"] == "sentarion_pro(email=...) for a trial key"
        assert "!" not in json.dumps(out), topic
    default = tool_json(_Result(asyncio.run(server.call_tool("sentarion_pro", {}))))
    assert set(default) == {"free_tier", "v2_paid_upgrade", "business_suite", "donate"}
    assert len(default["v2_paid_upgrade"]["what"]) == 8


class _Result:
    """Wrap a list[TextContent] so clients.tool_json can parse it."""

    def __init__(self, content):
        self.content = content
