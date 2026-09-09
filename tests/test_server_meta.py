"""WO-S1: server instructions, version unification, birth-fallback import."""

import sentarion_mcp
from sentarion_mcp import server


def test_instructions_content():
    for needle in ("rules, memory, and receipts", "sentarion_birth", "govern", "{{id}}", "Apache-2.0"):
        assert needle in server.INSTRUCTIONS


def test_instructions_length():
    assert len(server.INSTRUCTIONS) <= 1800


def test_version_unified():
    """One version everywhere: package == pyproject == server.json (top level and packages[])."""
    import json
    import re

    with open("pyproject.toml", encoding="utf-8") as fh:
        declared = re.search(r'^version = "([^"]+)"', fh.read(), re.M).group(1)
    assert sentarion_mcp.__version__ == declared
    with open("server.json", encoding="utf-8") as fh:
        sj = json.load(fh)
    assert sj["version"] == declared
    assert all(p["version"] == declared for p in sj["packages"])


def test_tool_text_importable():
    from sentarion_mcp.server import tool_text  # noqa: F401

    assert callable(tool_text)


def test_initialization_options_carry_instructions_and_version():
    opts = server.app.create_initialization_options()
    assert opts.instructions == server.INSTRUCTIONS
    assert opts.server_version == sentarion_mcp.__version__
