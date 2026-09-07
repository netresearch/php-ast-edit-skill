"""Keep main-loop usage separate from whole-call modelUsage (SDK documented scopes)."""

import math
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "agent-economics/efficiency")
)
import native


def summarize(events, requested_model):
    terminal = next(
        (row for row in reversed(events) if row.get("type") == "result"), None
    )
    init = next(
        (
            row
            for row in events
            if row.get("type") == "system" and row.get("subtype") == "init"
        ),
        None,
    )
    native.validate_init(init, requested_model)
    native.require(
        terminal is not None, "Missing native terminal result; spend is unknown"
    )
    models = terminal.get("modelUsage", {})
    totals = native.usage_totals(models)
    native.require(requested_model in models, "Requested model absent from final usage")
    usage = terminal.get("usage", {})
    main = {
        target: usage.get(source)
        for source, target in {
            **native.INPUT_KEYS,
            "output_tokens": "outputTokens",
        }.items()
    }
    main_totals = native.usage_totals({requested_model: main})
    remainder = {key: totals[key] - main_totals[key] for key in native.TOKEN_KEYS}
    native.require(
        all(value >= 0 for value in remainder.values()),
        "Main-loop usage exceeds whole-call model totals",
    )
    responses, calls, results = native.collect(events)
    native.require(set(calls) == set(results), "Native tool/result linkage incomplete")
    coverage = native.validate_inputs(
        responses, {requested_model: main}, requested_model, events
    )
    cost = terminal.get("total_cost_usd")
    native.require(
        type(cost) in (int, float) and math.isfinite(cost) and cost >= 0,
        "Native cost is unknown",
    )
    costs = [row.get("costUSD") for row in models.values()]
    native.require(
        all(
            type(value) in (int, float) and math.isfinite(value) and value >= 0
            for value in costs
        ),
        "Missing model costs",
    )
    native.require(
        math.isclose(sum(costs), cost, rel_tol=1e-9, abs_tol=1e-12),
        "Model costs and terminal cost differ",
    )
    return {
        **coverage,
        **native.tool_timings(events, calls),
        "reported_model": init["model"],
        "isolation_init": {
            key: init[key] for key in ("tools", "plugins", "skills", "mcp_servers")
        },
        "all_model_usage": models,
        "all_model_tokens": totals,
        "primary_model_tokens": native.usage_totals(
            {requested_model: models[requested_model]}
        ),
        "main_loop_tokens": main_totals,
        "whole_call_minus_main_loop": remainder,
        "auxiliary_work_attribution": "Not identified by the trace; no response count is inferred",
        "native_list_price_usd": cost,
        "native_subtype": terminal.get("subtype"),
        "native_is_error": terminal.get("is_error"),
        "native_num_turns": terminal.get("num_turns"),
        "native_duration_ms": terminal.get("duration_ms"),
        "native_duration_api_ms": terminal.get("duration_api_ms"),
        "per_response_inputs": responses,
        "initial_input_tokens": sum(next(iter(responses.values()))["input"].values()),
        "primary_model_rounds": len(responses),
        "tool_calls": len(calls),
        "failed_tool_calls": sum(bool(row.get("is_error")) for row in results.values()),
        "output_accounting": "Native result scopes: modelUsage for whole call; usage for main loop",
    }
