"""
sentarion seatbelt — deterministic editor hooks that make a coding agent remember the project
and ask before it breaks something.

Why this module exists (and why it is not another MCP tool): an MCP tool is only as safe as the
model's decision to call it. A Claude Code / Cursor *hook* runs on every tool call whether the
model remembers to ask or not. The seatbelt is that hook. It reuses the engine that already
exists — `govern_stub.infer_flags` for the risk vocabulary and the bundled ArkHive chain
(`arkhive_mcp.core`) for the tamper-evident record and the cross-session memory — and adds
nothing the MCP server does not already know how to do.

What it does, per hook event (Claude Code names; Cursor maps onto the same functions):

  pre   (PreToolUse)   match the tool call against the installed policies; deny / ask / allow.
  post  (PostToolUse)  record what happened (edit, command) so the next session can read it, and
                       note when a test/build/run command executes.
  start (SessionStart) print the project brief: what the last sessions edited, ran, decided and
                       where they were stopped — the agent starts with the plan, not from zero.
  stop  (Stop)         refuse to let the agent declare "done" when it edited code and never ran
                       anything, or when edited frontend files call routes no backend defines.

Policies are JSON files in ~/.sentarion/seatbelt/policies (see `POLICY_SCHEMA`). A baseline
policy is built in (the irreversible verbs the free gate already refuses) so an install with no
policy files still asks before `rm -rf`, `git push --force` and friends.

CLI (all behind the `sentarion` console script):
  sentarion seatbelt install   [--client claude|cursor|all] [--kit DIR] [--policies DIR] [--skills DIR]
  sentarion seatbelt uninstall [--client claude|cursor|all]
  sentarion seatbelt doctor
  sentarion seatbelt check  --tool Bash --command "rm -rf build"     (what would the gate say?)
  sentarion seatbelt recall [--project DIR] [-n 20]
  sentarion seatbelt policies
  sentarion seatbelt hook <pre|post|start|stop|cursor-shell|cursor-edit|cursor-stop>   (stdin JSON)

Apache-2.0, part of sentarion-mcp. Nothing here calls the network.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- paths / constants

ACTOR = "seatbelt"
COVENANT = ["ask before anything irreversible", "never move a secret", "remember the project", "test before done"]

HOME = Path(os.environ.get("SENTARION_SEATBELT_USER_HOME") or os.path.expanduser("~"))
SEATBELT_HOME = Path(os.environ.get("SENTARION_SEATBELT_HOME") or (HOME / ".sentarion" / "seatbelt"))
POLICY_DIR = SEATBELT_HOME / "policies"
SESSION_DIR = SEATBELT_HOME / "sessions"
CHAIN_DB = Path(os.environ.get("ARKHIVE_DB") or (HOME / ".sentarion" / "local_chamber.db"))

CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CLAUDE_JSON = HOME / ".claude.json"
CLAUDE_SKILLS = HOME / ".claude" / "skills"
CURSOR_HOOKS = HOME / ".cursor" / "hooks.json"
CURSOR_MCP = HOME / ".cursor" / "mcp.json"

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
MARK = "sentarion_mcp.seatbelt"   # every hook entry we own carries this in its args; uninstall keys off it

DECISION_RANK = {"allow": 0, "ask": 1, "deny": 2}

# The baseline: what the free gate refuses on sight (govern_stub._INFER["irreversible"] speaks the same
# vocabulary) expressed as shell patterns so an install with NO policy files still asks. Kit policies
# override by name; the baseline never denies on its own — a human yes is enough.
BASELINE_POLICY = {
    "name": "seatbelt-baseline",
    "version": 1,
    "why": "The obvious irreversible verbs, asked about even when no policy pack is installed.",
    "rules": [
        {
            "decision": "ask",
            "tools": list(SHELL_TOOLS),
            "match": [
                r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\b",
                r"\bRemove-Item\b[^|;\n]*-Recurse",
                r"\bgit\s+push\b[^|;\n]*(--force|-f)\b",
                r"\bgit\s+reset\s+--hard\b",
                r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",
                r"\bTRUNCATE\b",
                r"\bshred\b|\bmkfs\b|\bdd\s+if=",
            ],
            "reason": "This looks irreversible. Seatbelt is asking a human first (baseline policy).",
        }
    ],
    "on_stop": {
        "kind": "tests",
        "test_patterns": [
            r"\b(pytest|python\s+-m\s+pytest|unittest|tox|nox)\b",
            r"\b(npm|pnpm|yarn|bun)\s+(run\s+)?(test|build|lint|typecheck|check)\b",
            r"\b(npx|bunx)\s+(jest|vitest|mocha|playwright|cypress|tsc|eslint)\b",
            r"\bcargo\s+(test|build|check)\b|\bgo\s+(test|build|vet)\b|\bmake\s+(test|check|build)\b",
            r"\b(dotnet|mvn|gradle|gradlew)\s+(test|build)\b|\brspec\b|\bphpunit\b",
            r"\bcurl\b.*\b(localhost|127\.0\.0\.1)\b",
            r"\bpython3?\s+[^|;\n]*\.py\b|\bnode\s+[^|;\n]*\.(js|mjs|ts)\b",
            r"\bpython3?\s+-c\b|\bnode\s+-e\b|\bdeno\s+(run|test|eval)\b|\bbun\s+(run|test)\b|\bruby\s+-e\b|\bphp\s+-r\b",
        ],
        "code_globs": ["**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.go", "**/*.rs", "**/*.rb",
                       "**/*.php", "**/*.java", "**/*.cs", "**/*.vue", "**/*.svelte", "**/*.html", "**/*.css", "**/*.sql"],
        "reason": "You edited {n_edits} code file(s) this session ({files}) and no test, build or run command has "
                  "executed since the last edit. Run the tests (or build, or exercise the changed path) and report "
                  "the real output before declaring this done. If there are no tests, say so and show it running once.",
    },
}

POLICY_SCHEMA = {
    "name": "kebab-case, unique; a kit policy with the same name replaces the baseline",
    "version": 1,
    "why": "one sentence a buyer understands",
    "rules": [{
        "decision": "deny | ask | allow",
        "tools": ["Bash", "Edit", "Write", "MultiEdit", "NotebookEdit"],
        "match": ["regex applied to the shell command (Bash) or the file path (edit tools)"],
        "paths": ["glob applied to the file path, ** allowed"],
        "content_match": ["regex applied to the content being written"],
        "reason": "what the agent and the human are told",
    }],
    "on_stop": {"kind": "tests | wiring", "...": "see BASELINE_POLICY and the kit's 04/05 policies"},
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --------------------------------------------------------------------------- chain (memory + receipts)

def _core():
    """The bundled ArkHive chain, pointed at the same file the MCP server's local chamber uses, so the
    `recall` / `verify` tools see what the seatbelt wrote. Import is lazy: CHAIN_DB is fixed at import time."""
    os.environ.setdefault("ARKHIVE_DB", str(CHAIN_DB))
    from arkhive_mcp import core  # noqa: WPS433
    return core


def _ensure_born() -> str:
    core = _core()
    sid = core.resolve_actor(ACTOR)
    if sid:
        return sid
    return core.birth(ACTOR, COVENANT)["soul_id"]


def record(action: str, data: dict) -> dict:
    """Write one block. Never raises: a memory failure must not break the editor."""
    try:
        _ensure_born()
        return _core().remember(ACTOR, action, data)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def _project_of(cwd: str) -> str:
    """The git root when there is one, else the cwd — the memory key."""
    p = Path(cwd or ".").resolve()
    for cand in (p, *p.parents):
        if (cand / ".git").exists():
            return str(cand)
    return str(p)


def project_blocks(project: str, limit: int = 400) -> list[dict]:
    """Blocks the seatbelt wrote for this project, newest first. Reads the chain file directly (the core
    API has no data filter and a session brief must stay fast)."""
    import sqlite3
    if not CHAIN_DB.exists():
        return []
    needle = json.dumps(project)[1:-1]
    try:
        with sqlite3.connect(str(CHAIN_DB)) as c:
            rows = c.execute(
                "SELECT idx, ts, action, data FROM blocks WHERE actor LIKE ? AND data LIKE ? ORDER BY idx DESC LIMIT ?",
                (f"{ACTOR}-ri-%", f'%"project": "{needle}"%', limit),
            ).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for idx, ts, action, data in rows:
        try:
            d = json.loads(data)
        except ValueError:
            d = {"raw": data}
        out.append({"idx": idx, "ts": ts, "action": action, "data": d})
    return out


# --------------------------------------------------------------------------- policies

def _compile(p: str) -> re.Pattern:
    return re.compile(p, re.I | re.M)


def _glob_rx(g: str) -> re.Pattern:
    """`**/x` matches x at any depth, `**` inside matches any dirs, `*` never crosses a separator."""
    g = g.replace("\\", "/")
    out = ""
    i = 0
    while i < len(g):
        ch = g[i]
        if g.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if g.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if ch == "*":
            out += "[^/]*"
        elif ch == "?":
            out += "[^/]"
        else:
            out += re.escape(ch)
        i += 1
    return re.compile("^" + out + "$", re.I)


def path_matches(path: str, globs: list[str]) -> bool:
    p = str(path).replace("\\", "/")
    for g in globs or []:
        if _glob_rx(g).match(p) or _glob_rx(g).match(p.split("/")[-1]) or fnmatch.fnmatch(p, g):
            return True
    return False


def load_policies(policy_dir: Path | None = None) -> list[dict]:
    """Baseline first, then every *.json in the policy dir (sorted). A file whose name equals an earlier
    policy's name replaces it. Malformed files are skipped with a note in the policy's place."""
    d = policy_dir or POLICY_DIR
    policies: dict[str, dict] = {BASELINE_POLICY["name"]: BASELINE_POLICY}
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            try:
                pol = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(pol, dict) or not pol.get("name"):
                    raise ValueError("policy needs a name")
                pol["_file"] = str(f)
                policies[pol["name"]] = pol
            except Exception as e:  # noqa: BLE001
                policies[f.stem] = {"name": f.stem, "_error": f"{type(e).__name__}: {e}", "rules": []}
    # a kit's tests policy supersedes the baseline's on_stop of the same kind
    kinds = {p.get("on_stop", {}).get("kind") for n, p in policies.items() if n != BASELINE_POLICY["name"]}
    if "tests" in kinds:
        base = dict(BASELINE_POLICY)
        base.pop("on_stop", None)
        policies[BASELINE_POLICY["name"]] = base
    return list(policies.values())


def _tool_text(tool_name: str, tool_input: dict) -> tuple[str, str, str]:
    """(kind, primary text, content) for a tool call: shell → command; edit → path + written content."""
    if tool_name in SHELL_TOOLS:
        return "shell", str(tool_input.get("command") or ""), ""
    if tool_name in EDIT_TOOLS:
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or "")
        content = str(tool_input.get("new_string") or tool_input.get("content") or tool_input.get("new_source") or "")
        for e in tool_input.get("edits") or []:
            if isinstance(e, dict):
                content += "\n" + str(e.get("new_string") or "")
        return "edit", path, content
    return "other", json.dumps(tool_input, sort_keys=True)[:2000], ""


def evaluate(tool_name: str, tool_input: dict, policies: list[dict] | None = None) -> dict:
    """The gate. Returns {decision, reason, matched: [{policy, decision, pattern}], kind, text}."""
    pols = policies if policies is not None else load_policies()
    kind, text, content = _tool_text(tool_name, tool_input)
    matched: list[dict] = []
    for pol in pols:
        for rule in pol.get("rules") or []:
            tools = rule.get("tools") or []
            if tools and tool_name not in tools:
                continue
            decision = str(rule.get("decision") or "ask").lower()
            if decision not in DECISION_RANK:
                continue
            hit = None
            if kind == "shell":
                for pat in rule.get("match") or []:
                    if _compile(pat).search(text):
                        hit = pat
                        break
            elif kind == "edit":
                if rule.get("paths") and path_matches(text, rule["paths"]):
                    hit = "path:" + ";".join(rule["paths"])[:80]
                if hit is None:
                    for pat in rule.get("match") or []:
                        if _compile(pat).search(text):
                            hit = pat
                            break
                if hit is None and content:
                    for pat in rule.get("content_match") or []:
                        if _compile(pat).search(content):
                            hit = "content:" + pat
                            break
            if hit is not None:
                matched.append({"policy": pol["name"], "decision": decision, "pattern": hit,
                                "reason": rule.get("reason") or pol.get("why") or pol["name"]})
    if not matched:
        return {"decision": "allow", "reason": "no policy matched", "matched": [], "kind": kind, "text": text}
    top = max(matched, key=lambda m: DECISION_RANK[m["decision"]])
    names = sorted({m["policy"] for m in matched if m["decision"] == top["decision"]})
    reason = top["reason"]
    if len(names) > 1:
        reason += " (policies: " + ", ".join(names) + ")"
    return {"decision": top["decision"], "reason": reason, "matched": matched, "kind": kind, "text": text}


# --------------------------------------------------------------------------- session state

def _session_path(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return SESSION_DIR / f"{safe}.json"


def load_session(session_id: str) -> dict:
    p = _session_path(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"session_id": session_id, "started": _now(), "edits": [], "commands": [], "gate": [],
            "last_edit": None, "last_test": None, "stop_blocks": {}}


def save_session(state: dict) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _session_path(state["session_id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, _session_path(state["session_id"]))


# --------------------------------------------------------------------------- hooks

def _read_stdin() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def hook_pre(payload: dict, policies: list[dict] | None = None) -> dict | None:
    """PreToolUse. Returns the JSON to print (None = allow silently)."""
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool not in SHELL_TOOLS + EDIT_TOOLS:
        return None
    verdict = evaluate(tool, tool_input, policies)
    if verdict["decision"] == "allow":
        return None
    project = _project_of(str(payload.get("cwd") or ""))
    entry = {"ts": _now(), "tool": tool, "decision": verdict["decision"], "text": verdict["text"][:300],
             "policies": sorted({m["policy"] for m in verdict["matched"]})}
    state = load_session(str(payload.get("session_id") or ""))
    state["gate"].append(entry)
    save_session(state)
    receipt = record("gate:" + verdict["decision"], {"project": project, **entry})
    reason = verdict["reason"]
    if verdict["decision"] == "deny":
        reason += " Do not retry it under another name or work around it; tell the user what you wanted to do and why."
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": verdict["decision"],
                                   "permissionDecisionReason": reason},
            "seatbelt": {"policies": entry["policies"], "recorded": "idx" in receipt}}


def _is_test_command(cmd: str, policies: list[dict]) -> bool:
    for pol in policies:
        stop = pol.get("on_stop") or {}
        if stop.get("kind") == "tests":
            for pat in stop.get("test_patterns") or []:
                if _compile(pat).search(cmd):
                    return True
    return False


def hook_post(payload: dict, policies: list[dict] | None = None) -> dict | None:
    """PostToolUse. Records edits and commands; notes test runs. Never blocks (the action already ran)."""
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict) or tool not in SHELL_TOOLS + EDIT_TOOLS:
        return None
    pols = policies if policies is not None else load_policies()
    project = _project_of(str(payload.get("cwd") or ""))
    state = load_session(str(payload.get("session_id") or ""))
    kind, text, _ = _tool_text(tool, tool_input)
    ts = _now()
    if kind == "edit" and text:
        rel = _relative(text, project)
        state["edits"].append({"ts": ts, "path": rel, "tool": tool})
        state["last_edit"] = ts
        record("edit", {"project": project, "path": rel, "tool": tool, "session": state["session_id"]})
    elif kind == "shell" and text:
        resp = payload.get("tool_response")
        failed = _looks_failed(resp)
        state["commands"].append({"ts": ts, "cmd": text[:200], "failed": failed})
        if _is_test_command(text, pols):
            state["last_test"] = ts
            state["last_test_failed"] = failed
        record("command", {"project": project, "cmd": text[:200], "failed": failed, "session": state["session_id"]})
    save_session(state)
    return None


def _looks_failed(resp: Any) -> bool | None:
    """Best effort from the tool_response shape Claude Code passes (dict with exit_code / is_error, or text)."""
    if isinstance(resp, dict):
        if resp.get("is_error") is True:
            return True
        code = resp.get("exit_code")
        if isinstance(code, int):
            return code != 0
        text = str(resp.get("stdout") or resp.get("output") or resp.get("content") or "")
    else:
        text = str(resp or "")
    if re.search(r"\b(\d+) failed\b|\bFAILED\b|\bError:|\bTraceback \(most recent", text):
        return True
    return None


def _relative(path: str, project: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(project).resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return str(path).replace("\\", "/")


def brief(project: str, limit_blocks: int = 400) -> str:
    """The session-start text: what happened here before, in the order an engineer would want it."""
    blocks = project_blocks(project, limit_blocks)
    pols = load_policies()
    names = [p["name"] for p in pols if not p.get("_error")]
    bad = [p["name"] for p in pols if p.get("_error")]
    lines = [f"Sentarion Seatbelt is on for {project}.",
             f"Policies active: {', '.join(names)}." + (f" Could not load: {', '.join(bad)}." if bad else "")]
    if not blocks:
        lines.append("No earlier sessions recorded for this project yet. Whatever you do here today will be "
                     "read back at the next session start.")
    else:
        edits = [b for b in blocks if b["action"] == "edit"]
        cmds = [b for b in blocks if b["action"] == "command"]
        decisions = [b for b in blocks if b["action"].startswith(("decision", "milestone", "note", "plan"))]
        gates = [b for b in blocks if b["action"].startswith("gate:")]
        ends = [b for b in blocks if b["action"] == "session_end"]
        last = blocks[0]["ts"]
        lines.append(f"Last activity here: {last} ({len(blocks)} records).")
        if ends:
            e = ends[0]["data"]
            lines.append("Last session ended: " + (e.get("summary") or "no summary") +
                         (" — it was told to test before finishing and did not." if e.get("untested") else ""))
        if decisions:
            lines.append("Decisions and milestones on record (newest first):")
            for b in decisions[:8]:
                d = b["data"]
                what = d.get("what") or d.get("decision") or d.get("text") or json.dumps({k: v for k, v in d.items() if k != "project"})[:160]
                lines.append(f"  - {b['ts'][:10]} {b['action']}: {what}")
        if edits:
            seen: list[str] = []
            for b in edits:
                p = b["data"].get("path")
                if p and p not in seen:
                    seen.append(p)
            lines.append("Files edited in earlier sessions (most recent first): " + ", ".join(seen[:12]) +
                         (f" (+{len(seen) - 12} more)" if len(seen) > 12 else ""))
        if cmds:
            recent = [b["data"].get("cmd", "") for b in cmds[:6]]
            lines.append("Last commands run: " + " | ".join(c[:70] for c in recent))
            failed = [b["data"].get("cmd", "") for b in cmds[:30] if b["data"].get("failed")]
            if failed:
                lines.append("Commands that failed last time (check before repeating): " + " | ".join(c[:70] for c in failed[:4]))
        if gates:
            g = gates[0]["data"]
            lines.append(f"Last gate event: {gates[0]['action']} on `{g.get('text', '')[:80]}` ({', '.join(g.get('policies', []))}).")
    lines.append("Keep the memory honest: when you decide something or finish a milestone, call the sentarion MCP tool "
                 "`remember` with actor \"seatbelt\", action \"decision: <what>\" (or \"milestone: <what>\") and data "
                 "{\"project\": \"" + project.replace("\\", "/") + "\"}. It is read back here next time. "
                 "Before anything irreversible, expect the seatbelt to ask; a deny is final.")
    return "\n".join(lines)


def hook_start(payload: dict) -> dict:
    project = _project_of(str(payload.get("cwd") or ""))
    text = brief(project)
    state = load_session(str(payload.get("session_id") or ""))
    state["project"] = project
    state["source"] = payload.get("source")
    save_session(state)
    record("session_start", {"project": project, "session": state["session_id"], "source": payload.get("source")})
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def _routes_in(text: str, patterns: list[str]) -> set[str]:
    found: set[str] = set()
    for pat in patterns:
        try:
            rx = _compile(pat)
        except re.error:
            continue
        for m in rx.finditer(text):
            route = next((g for g in m.groups()[::-1] if g), None) if m.groups() else m.group(0)
            if route and route.startswith("/") and len(route) < 120:
                found.add(route.rstrip("/"))
    return found


def _iter_files(root: Path, globs: list[str], exclude: list[str], cap: int = 3000):
    n = 0
    for p in root.rglob("*"):
        if n >= cap:
            return
        if not p.is_file():
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if path_matches(rel, exclude):
            continue
        if path_matches(rel, globs):
            n += 1
            yield p


def wiring_check(project: str, edited: list[str], stop: dict) -> dict:
    """Routes the edited frontend files call vs. the strings present anywhere in the backend files."""
    root = Path(project)
    fe = [e for e in edited if path_matches(e, stop.get("frontend_globs") or [])]
    if not fe:
        return {"routes": [], "missing": [], "found": []}
    routes: set[str] = set()
    for rel in fe:
        p = root / rel
        try:
            routes |= _routes_in(p.read_text(encoding="utf-8", errors="replace"), stop.get("route_patterns") or [])
        except OSError:
            continue
    if not routes:
        return {"routes": [], "missing": [], "found": []}
    exclude = stop.get("exclude_globs") or []
    haystack = []
    for p in _iter_files(root, stop.get("backend_globs") or [], exclude):
        rel = str(p.relative_to(root)).replace("\\", "/")
        if rel in fe:
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
            haystack.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    blob = "\n".join(haystack)
    found, missing = [], []
    for r in sorted(routes):
        # a route is "found" if its path, or its path with the last segment as a parameter, appears server-side
        tail = r.rsplit("/", 1)
        candidates = [r, r.lstrip("/")] + ([tail[0]] if len(tail) == 2 and tail[0] else [])
        (found if any(c and c in blob for c in candidates) else missing).append(r)
    return {"routes": sorted(routes), "missing": missing, "found": found}


def hook_stop(payload: dict, policies: list[dict] | None = None) -> dict | None:
    """Stop. Block once per check kind per session; then let go and record the session summary."""
    pols = policies if policies is not None else load_policies()
    sid = str(payload.get("session_id") or "")
    state = load_session(sid)
    project = state.get("project") or _project_of(str(payload.get("cwd") or ""))
    edits = [e["path"] for e in state.get("edits") or []]
    blocks = state.setdefault("stop_blocks", {})
    for pol in pols:
        stop = pol.get("on_stop") or {}
        kind = stop.get("kind")
        if not kind or blocks.get(kind):
            continue
        reason = None
        if kind == "tests":
            code_edits = [e for e in edits if path_matches(e, stop.get("code_globs") or ["**/*"])]
            if code_edits and (not state.get("last_test") or state["last_test"] < (state.get("last_edit") or "")):
                uniq = list(dict.fromkeys(code_edits))
                reason = (stop.get("reason") or BASELINE_POLICY["on_stop"]["reason"]).format(
                    n_edits=len(uniq), files=", ".join(uniq[:6]) + (" …" if len(uniq) > 6 else ""))
            elif code_edits and state.get("last_test_failed"):
                reason = ("The last test/build command you ran failed and you have not run one since. "
                          "Fix it and run it again, or say plainly that it is failing and why.")
        elif kind == "wiring" and edits:
            w = wiring_check(project, list(dict.fromkeys(edits)), stop)
            if w["missing"]:
                reason = (stop.get("reason") or "Routes not found in the backend: {missing}").format(
                    missing=", ".join(w["missing"]), found=", ".join(w["found"]) or "none")
        if reason:
            blocks[kind] = _now()
            save_session(state)
            record("stop_block", {"project": project, "kind": kind, "policy": pol["name"], "session": sid})
            return {"decision": "block", "reason": f"[seatbelt · {pol['name']}] {reason}"}
    # letting go: write the memory the next session reads
    uniq = list(dict.fromkeys(edits))
    untested = bool(uniq) and (not state.get("last_test") or state["last_test"] < (state.get("last_edit") or ""))
    summary = (f"{len(uniq)} file(s) edited" + (": " + ", ".join(uniq[:5]) if uniq else "") +
               f"; {len(state.get('commands') or [])} command(s) run; gate events: {len(state.get('gate') or [])}")
    if not state.get("ended"):
        record("session_end", {"project": project, "session": sid, "summary": summary, "untested": untested,
                               "edits": uniq[:40]})
        state["ended"] = _now()
        save_session(state)
    return None


# --------------------------------------------------------------------------- Cursor adapters (beta)

def hook_cursor_shell(payload: dict) -> dict:
    """Cursor beforeShellExecution: {command, cwd, ...} → {permission: allow|deny|ask, agent_message, user_message}."""
    fake = {"session_id": payload.get("conversation_id") or payload.get("session_id") or "cursor",
            "cwd": payload.get("cwd") or (payload.get("workspace_roots") or [""])[0],
            "tool_name": "Bash", "tool_input": {"command": payload.get("command") or ""}}
    out = hook_pre(fake)
    if not out:
        return {"permission": "allow"}
    h = out["hookSpecificOutput"]
    return {"permission": h["permissionDecision"], "agent_message": h["permissionDecisionReason"],
            "user_message": h["permissionDecisionReason"]}


def hook_cursor_edit(payload: dict) -> None:
    fake = {"session_id": payload.get("conversation_id") or "cursor",
            "cwd": payload.get("cwd") or (payload.get("workspace_roots") or [""])[0],
            "tool_name": "Edit", "tool_input": {"file_path": payload.get("file_path") or ""}}
    hook_post(fake)
    return None


def hook_cursor_stop(payload: dict) -> dict | None:
    fake = {"session_id": payload.get("conversation_id") or "cursor",
            "cwd": payload.get("cwd") or (payload.get("workspace_roots") or [""])[0]}
    out = hook_stop(fake)
    if out:
        return {"followup_message": out["reason"]}
    return None


HOOKS = {"pre": hook_pre, "post": hook_post, "start": hook_start, "stop": hook_stop,
         "cursor-shell": hook_cursor_shell, "cursor-edit": hook_cursor_edit, "cursor-stop": hook_cursor_stop}


def run_hook(event: str) -> int:
    fn = HOOKS.get(event)
    if not fn:
        print(json.dumps({"error": f"unknown hook event {event}", "events": sorted(HOOKS)}))
        return 1
    try:
        out = fn(_read_stdin())
    except Exception as e:  # noqa: BLE001
        # a broken seatbelt must never brick the editor: fail open on our own bugs, loudly on stderr
        sys.stderr.write(f"seatbelt {event} hook error: {type(e).__name__}: {e}\n")
        return 1
    if out is not None:
        sys.stdout.write(json.dumps(out))
    return 0


# --------------------------------------------------------------------------- install / uninstall / doctor

def _load_json(p: Path) -> dict:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8") or "{}")
        except ValueError:
            bak = p.with_suffix(p.suffix + f".bak-seatbelt-{int(time.time())}")
            shutil.copy2(p, bak)
            return {}
    return {}


def _save_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak-seatbelt"))
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _hook_entry(python: str, event: str, timeout: int) -> dict:
    return {"type": "command", "command": python, "args": ["-m", MARK, "hook", event], "timeout": timeout}


def _ours(h: dict) -> bool:
    return isinstance(h, dict) and MARK in " ".join(str(a) for a in (h.get("args") or [])) or MARK in str(h.get("command", ""))


CLAUDE_EVENTS = {
    "PreToolUse": ("Bash|Edit|Write|MultiEdit|NotebookEdit", "pre", 20),
    "PostToolUse": ("Bash|Edit|Write|MultiEdit|NotebookEdit", "post", 20),
    "SessionStart": ("", "start", 20),
    "Stop": ("", "stop", 60),
}


def install_claude(python: str, settings: Path = CLAUDE_SETTINGS) -> dict:
    data = _load_json(settings)
    hooks = data.setdefault("hooks", {})
    for event, (matcher, ours, timeout) in CLAUDE_EVENTS.items():
        groups = [g for g in hooks.get(event) or [] if not any(_ours(h) for h in (g.get("hooks") or []))]
        group = {"hooks": [_hook_entry(python, ours, timeout)]}
        if matcher:
            group["matcher"] = matcher
        groups.append(group)
        hooks[event] = groups
    _save_json(settings, data)
    return {"settings": str(settings), "events": list(CLAUDE_EVENTS)}


def uninstall_claude(settings: Path = CLAUDE_SETTINGS) -> dict:
    data = _load_json(settings)
    hooks = data.get("hooks") or {}
    removed = 0
    for event in list(hooks):
        keep = []
        for g in hooks[event]:
            if any(_ours(h) for h in (g.get("hooks") or [])):
                removed += 1
            else:
                keep.append(g)
        if keep:
            hooks[event] = keep
        else:
            hooks.pop(event)
    _save_json(settings, data)
    return {"settings": str(settings), "removed_groups": removed}


def install_mcp_claude(python: str, claude_json: Path = CLAUDE_JSON) -> dict:
    """Register the `sentarion` stdio server in the user scope. A `sentarion` entry the user configured
    themselves (anything we did not write) is kept untouched and reported — never clobbered."""
    data = _load_json(claude_json)
    servers = data.setdefault("mcpServers", {})
    existing = servers.get("sentarion")
    if existing and list(existing.get("args") or []) != ["-m", "sentarion_mcp.server"]:
        return {"file": str(claude_json), "server": "sentarion", "kept_existing": existing.get("command"),
                "note": "a sentarion MCP server was already configured; left as is"}
    servers["sentarion"] = {"type": "stdio", "command": python, "args": ["-m", "sentarion_mcp.server"], "env": {}}
    _save_json(claude_json, data)
    return {"file": str(claude_json), "server": "sentarion"}


def install_skills(src: Path, dst: Path = CLAUDE_SKILLS) -> dict:
    copied = []
    if src and src.is_dir():
        for d in sorted(src.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                target = dst / d.name
                target.mkdir(parents=True, exist_ok=True)
                for f in d.iterdir():
                    if f.is_file():
                        shutil.copy2(f, target / f.name)
                copied.append(d.name)
    return {"dir": str(dst), "skills": copied}


def install_policies(src: Path | None, dst: Path = POLICY_DIR, force: bool = False) -> dict:
    dst.mkdir(parents=True, exist_ok=True)
    installed, kept = [], []
    if src and src.is_dir():
        for f in sorted(src.glob("*.json")):
            target = dst / f.name
            if target.exists() and not force:
                try:
                    old_v = json.loads(target.read_text(encoding="utf-8")).get("version", 0)
                    new_v = json.loads(f.read_text(encoding="utf-8")).get("version", 0)
                except ValueError:
                    old_v, new_v = 0, 1
                if old_v >= new_v:
                    kept.append(f.name)
                    continue
                shutil.copy2(target, target.with_suffix(".json.bak"))
            shutil.copy2(f, target)
            installed.append(f.name)
    return {"dir": str(dst), "installed": installed, "kept_existing": kept}


CURSOR_EVENTS = {"beforeShellExecution": "cursor-shell", "afterFileEdit": "cursor-edit", "stop": "cursor-stop"}


def install_cursor(python: str, hooks_file: Path = CURSOR_HOOKS, mcp_file: Path = CURSOR_MCP) -> dict:
    data = _load_json(hooks_file)
    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    for event, ours in CURSOR_EVENTS.items():
        lst = [h for h in hooks.get(event) or [] if not _ours(h)]
        # Cursor runs `command` through a shell: quote the interpreter path
        lst.append({"command": f'"{python}" -m {MARK} hook {ours}'})
        hooks[event] = lst
    _save_json(hooks_file, data)
    mcp = _load_json(mcp_file)
    mcp.setdefault("mcpServers", {})["sentarion"] = {"command": python, "args": ["-m", "sentarion_mcp.server"]}
    _save_json(mcp_file, mcp)
    return {"hooks": str(hooks_file), "mcp": str(mcp_file), "note": "Cursor hooks are beta: Cursor's stdin/stdout contract is documented at cursor.com/docs/hooks; verify with `sentarion seatbelt doctor`"}


def uninstall_cursor(hooks_file: Path = CURSOR_HOOKS) -> dict:
    data = _load_json(hooks_file)
    hooks = data.get("hooks") or {}
    removed = 0
    for event in list(hooks):
        keep = [h for h in hooks[event] if not _ours(h)]
        removed += len(hooks[event]) - len(keep)
        if keep:
            hooks[event] = keep
        else:
            hooks.pop(event)
    _save_json(hooks_file, data)
    return {"hooks": str(hooks_file), "removed": removed}


def self_test(python: str) -> dict:
    """Pipe a dangerous PreToolUse through the exact command the editor will run; expect a deny or ask."""
    payload = {"session_id": "seatbelt-selftest", "cwd": str(Path.cwd()), "tool_name": "Bash",
               "tool_input": {"command": "rm -rf / --no-preserve-root"}}
    env = dict(os.environ)
    env["SENTARION_SEATBELT_HOME"] = str(SEATBELT_HOME)
    try:
        r = subprocess.run([python, "-m", MARK, "hook", "pre"], input=json.dumps(payload), capture_output=True,
                           text=True, timeout=30, env=env)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        out = json.loads(r.stdout or "{}")
        decision = out["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError):
        return {"ok": False, "stdout": r.stdout[:300], "stderr": r.stderr[:300], "exit": r.returncode}
    return {"ok": decision in ("deny", "ask"), "decision": decision, "exit": r.returncode}


def doctor(python: str | None = None) -> dict:
    py = python or sys.executable
    pols = load_policies()
    claude = _load_json(CLAUDE_SETTINGS)
    wired = {ev: any(_ours(h) for g in (claude.get("hooks") or {}).get(ev, []) for h in g.get("hooks") or [])
             for ev in CLAUDE_EVENTS}
    mcp = "sentarion" in (_load_json(CLAUDE_JSON).get("mcpServers") or {})
    cursor = _load_json(CURSOR_HOOKS)
    cursor_wired = any(_ours(h) for lst in (cursor.get("hooks") or {}).values() for h in lst)
    skills = sorted(d.name for d in CLAUDE_SKILLS.iterdir() if (d / "SKILL.md").exists()) if CLAUDE_SKILLS.is_dir() else []
    try:
        verify = _core().verify()
    except Exception as e:  # noqa: BLE001
        verify = {"error": f"{type(e).__name__}: {e}"}
    st = self_test(py)
    ready = all(wired.values()) and st.get("ok", False)
    return {"ready": ready, "python": py, "claude_hooks": wired, "claude_mcp_server": mcp,
            "cursor_hooks": cursor_wired, "skills": skills,
            "policies": [{"name": p["name"], "rules": len(p.get("rules") or []), "on_stop": (p.get("on_stop") or {}).get("kind"),
                          "error": p.get("_error")} for p in pols],
            "policy_dir": str(POLICY_DIR), "chain": {"db": str(CHAIN_DB), **verify}, "self_test": st,
            "next_steps": [] if ready else ["run: sentarion seatbelt install --client claude"]}


def install(args: argparse.Namespace) -> dict:
    py = args.python or sys.executable
    kit = Path(args.kit) if args.kit else None
    policies_src = Path(args.policies) if args.policies else (kit / "policies" if kit else None)
    skills_src = Path(args.skills) if args.skills else (kit / "skills" if kit else None)
    out: dict[str, Any] = {"python": py}
    SEATBELT_HOME.mkdir(parents=True, exist_ok=True)
    out["actor"] = _ensure_born()
    out["policies"] = install_policies(policies_src, force=args.force)
    if args.client in ("claude", "all"):
        out["claude"] = install_claude(py)
        if not args.no_mcp:
            out["claude_mcp"] = install_mcp_claude(py)
        if skills_src:
            out["skills"] = install_skills(skills_src)
    if args.client in ("cursor", "all"):
        out["cursor"] = install_cursor(py)
    out["self_test"] = self_test(py)
    record("installed", {"project": "*", "client": args.client, "policies": out["policies"]["installed"]})
    out["ready"] = bool(out["self_test"].get("ok"))
    out["next"] = ("Open Claude Code in any project. The session starts with the project brief; try asking it to "
                   "`rm -rf` something and watch the seatbelt ask." if out["ready"] else
                   "Self-test failed: run `sentarion seatbelt doctor` and send the output to support.")
    return out


def uninstall(args: argparse.Namespace) -> dict:
    out: dict[str, Any] = {}
    if args.client in ("claude", "all"):
        out["claude"] = uninstall_claude()
    if args.client in ("cursor", "all"):
        out["cursor"] = uninstall_cursor()
    out["note"] = f"policies and memory were kept in {SEATBELT_HOME} and {CHAIN_DB}; delete them by hand if you want them gone"
    return out


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sentarion seatbelt", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("install", help="wire the hooks, the MCP server, the policies and the skills")
    i.add_argument("--client", choices=["claude", "cursor", "all"], default="claude")
    i.add_argument("--kit", help="kit directory holding policies/ and skills/")
    i.add_argument("--policies", help="policy directory (overrides --kit)")
    i.add_argument("--skills", help="skills directory (overrides --kit)")
    i.add_argument("--python", help="interpreter the hooks run with (default: this one)")
    i.add_argument("--no-mcp", action="store_true", help="do not register the sentarion MCP server")
    i.add_argument("--force", action="store_true", help="overwrite policy files you edited")
    u = sub.add_parser("uninstall", help="remove the hooks (keeps policies and memory)")
    u.add_argument("--client", choices=["claude", "cursor", "all"], default="all")
    d = sub.add_parser("doctor", help="what is wired, what the policies are, and a live self-test")
    d.add_argument("--python")
    c = sub.add_parser("check", help="what would the gate say to this tool call?")
    c.add_argument("--tool", default="Bash")
    c.add_argument("--command", help="shell command (Bash)")
    c.add_argument("--path", help="file path (edit tools)")
    c.add_argument("--content", default="", help="content being written (edit tools)")
    r = sub.add_parser("recall", help="the project brief the next session will see")
    r.add_argument("--project", default=".")
    r.add_argument("-n", type=int, default=400)
    sub.add_parser("policies", help="list the loaded policies")
    h = sub.add_parser("hook", help="(called by the editor) read the event JSON on stdin")
    h.add_argument("event", choices=sorted(HOOKS))
    a = ap.parse_args(argv)

    if a.cmd == "hook":
        return run_hook(a.event)
    if a.cmd == "install":
        print(json.dumps(install(a), indent=2))
        return 0
    if a.cmd == "uninstall":
        print(json.dumps(uninstall(a), indent=2))
        return 0
    if a.cmd == "doctor":
        rep = doctor(a.python)
        print(json.dumps(rep, indent=2))
        return 0 if rep["ready"] else 1
    if a.cmd == "check":
        if a.tool in SHELL_TOOLS:
            ti = {"command": a.command or ""}
        else:
            ti = {"file_path": a.path or "", "content": a.content}
        v = evaluate(a.tool, ti)
        print(json.dumps({k: v[k] for k in ("decision", "reason", "matched")}, indent=2))
        return 0
    if a.cmd == "recall":
        print(brief(_project_of(a.project), a.n))
        return 0
    if a.cmd == "policies":
        for p in load_policies():
            flag = f"  [BROKEN: {p['_error']}]" if p.get("_error") else ""
            print(f"{p['name']}  rules={len(p.get('rules') or [])}  on_stop={(p.get('on_stop') or {}).get('kind') or '-'}"
                  f"  {p.get('_file', '(built in)')}{flag}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
