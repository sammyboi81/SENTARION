"""
Cost prediction, before-the-fact — the feature LeoDg's orchestrator-mcp-server
markets as "ML-based cost estimation." This is a simple, transparent estimate
(not ML) built from numbers Algernon's own README already publishes, so it's
grounded rather than invented:

    Algernon's published benchmark (llama3.2:3b, 6 tasks):
      input tokens: 225 total  -> ~37.5 per task
      output tokens: 279 total -> ~46.5 per task

We scale those per-task averages by k (task count) and let the caller
override with real numbers once they have them from their own provider/model.
"""

from __future__ import annotations

# From Algernon's published verify.sh benchmark — update if their numbers change.
AVG_INPUT_TOKENS_PER_TASK = 37.5
AVG_OUTPUT_TOKENS_PER_TASK = 46.5


def estimate_dispatch_cost(
    k_tasks: int,
    input_price_per_mtok: float,
    output_price_per_mtok: float,
) -> dict:
    """
    Rough pre-dispatch cost estimate for k Algernon fan-out tasks.

    Prices are per-million-tokens, in whatever currency the caller uses
    (matches Anthropic/OpenAI pricing page conventions).
    """
    est_input = AVG_INPUT_TOKENS_PER_TASK * k_tasks
    est_output = AVG_OUTPUT_TOKENS_PER_TASK * k_tasks
    est_cost = (est_input / 1_000_000) * input_price_per_mtok + (
        est_output / 1_000_000
    ) * output_price_per_mtok

    return {
        "k_tasks": k_tasks,
        "estimated_input_tokens": round(est_input),
        "estimated_output_tokens": round(est_output),
        "estimated_cost": round(est_cost, 6),
        "basis": "Extrapolated from Algernon's published verify.sh benchmark "
        "(llama3.2:3b, 6 tasks) — actual cost varies by model and task complexity.",
    }
