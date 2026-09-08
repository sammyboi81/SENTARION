TASK:
Add a CI test job and bump the package to 0.3.0 everywhere versions are declared. Do not publish.

WHY:
The only workflow today publishes server.json metadata and runs no tests. Week-1 work (WO-S1..S4) must be verified on every push. 0.3.0 is the release that carries instructions, doctor, quickstart, run summary, examples.

KNOWN FACTS:
- .github/workflows/mcp-publish.yml publishes server.json to the MCP Registry via GitHub OIDC on pushes touching server.json or the workflow. It runs no build or tests.
- Version strings: pyproject.toml `version`, sentarion_mcp/__init__.py `__version__`, server.json top-level `version` and packages[0].version, README title area, smithery.yaml (check for a version field; UNKNOWN until inspected), glama.json (check likewise).
- Tests live in tests/ and run with `python -m pytest -q` (pytest configured in pyproject by WO-S1).
- Python requirement is >=3.10.

UNKNOWNS:
- Whether smithery.yaml / glama.json carry a version; inspect and report.

FILES ALLOWED:
- .github/workflows/test.yml (new)
- pyproject.toml (version only)
- sentarion_mcp/__init__.py (version only)
- server.json (version fields only)
- README.md (ONLY: add a "0.3.0" changelog entry above "0.2.2" listing: server instructions, sentarion_doctor, sentarion_quickstart, run summary with run_id and memory outcome, contextual sentarion_pro, examples/, tests + CI, birth fallback fix, version unification)
- smithery.yaml, glama.json (version field only, if present)

FILES FORBIDDEN:
- all other files; do not touch mcp-publish.yml.

CURRENT BEHAVIOR:
- No test CI. Version 0.2.2.

REQUIRED BEHAVIOR:
1. .github/workflows/test.yml: on push and pull_request to any branch; matrix python 3.10, 3.12; steps: checkout, setup-python, `pip install -e . pytest`, `python -m pytest -q`, and a final step `python -c "import sentarion_mcp, tomllib, json; v=sentarion_mcp.__version__; assert v==tomllib.load(open('pyproject.toml','rb'))['project']['version']; assert v==json.load(open('server.json'))['version']"` so version drift fails CI.
2. Set 0.3.0 in every declared location listed above.
3. README changelog entry as specified.

DATA CONTRACT:
- none.

UX REQUIREMENTS:
- none.

ERROR STATES:
- CI red on any test failure or version drift.

SECURITY / PERMISSIONS:
- No publish step. No secrets in the workflow.

TESTS REQUIRED:
- `python -m pytest -q` locally passes.
- The version-consistency one-liner passes locally.

ACCEPTANCE CRITERIA:
1. Both commands above pass.
2. `grep -rn "0.2.2" --include=*.py --include=*.toml --include=*.json .` returns only changelog/history mentions, none in version fields.
3. Changed files are a subset of FILES ALLOWED.

DO NOT:
- publish to PyPI or the MCP Registry
- change mcp-publish.yml
- commit

RETURN:
- concise implementation summary
- files changed
- commands run and results
- whether smithery.yaml / glama.json carried a version
- failures / blockers
