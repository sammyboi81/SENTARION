"""
Algernon's `algernon_dispatch` runs tasks concurrently with no ordering —
by design, for tight independent scoping. This adds an optional
`depends_on` layer on top (task-orchestrator's fan-out/fan-in pattern,
reimplemented here — not copied, since that project is a separate
Kotlin/JVM codebase we don't import).

Tasks with no dependencies all run in "wave 1". Once a wave completes,
any task whose dependencies are now satisfied joins the next wave.
Circular dependencies raise before anything dispatches.
"""

from __future__ import annotations

from typing import TypedDict


class Task(TypedDict):
    id: str
    prompt: str
    depends_on: list[str]  # ids of tasks that must complete first; [] = no deps


def resolve_waves(tasks: list[Task]) -> list[list[Task]]:
    """Splits tasks into ordered waves respecting depends_on. Raises on cycles."""
    remaining = {t["id"]: t for t in tasks}
    done: set[str] = set()
    waves: list[list[Task]] = []

    while remaining:
        ready = [
            t for t in remaining.values() if all(d in done for d in t["depends_on"])
        ]
        if not ready:
            stuck = list(remaining.keys())
            raise ValueError(f"Circular or unsatisfiable dependency among tasks: {stuck}")

        waves.append(ready)
        for t in ready:
            done.add(t["id"])
            del remaining[t["id"]]

    return waves
