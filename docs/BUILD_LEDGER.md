# Sentarion OSS — Build Ledger (week 1)

Source of truth: docs/truth/SENTARION_V2_PAID_OSS_AND_DOGFOOD_GTM.md (§25 OSS patches, §44 week 1, §47 build order).
Orchestrator: Claude Code. Implementer: Codex (`codex exec`, sandbox workspace-write, cwd = this worktree).
Base SHA: 6e227e6. Branch: week1-oss-patches. Worktree: C:\Users\tiger\sentarion-week1.

| TASK | STATUS | FILES TOUCHED | DEPENDENCIES | ASSUMPTIONS | TESTS | RESULT | OPEN RISKS |
|---|---|---|---|---|---|---|---|
| WO-S1 server instructions + birth NameError fix + version/dist hygiene | queued | server.py, __init__.py, .gitignore, dist/, tests/ | none | mcp SDK Server accepts instructions= and version= (verified in installed SDK) | tests/test_server_meta.py | - | none |
| WO-S2 sentarion_doctor | queued | doctor.py (new), server.py (register), tests/test_doctor.py | WO-S1 | probes are short-timeout and never raise | tests/test_doctor.py | - | must never print secret values |
| WO-S3 quickstart tool + run summary + contextual sentarion_pro | queued | quickstart.py (new), server.py, tests/ | WO-S2 | - | tests | - | sentarion_pro stays honest, no dark patterns |
| WO-S4 examples/ + README positioning + waitlist CTA | queued | examples/**, README.md, server.json (description only) | WO-S3 | examples runnable with `sentarion` on PATH | examples smoke test | - | README must not claim dogfood metrics |
| WO-S5 CI test job + version 0.3.0 | queued | .github/workflows/*.yml, pyproject.toml, __init__.py, server.json | WO-S4 | PyPI publish stays manual (founder-gated) | `python -m pytest` green | - | - |
