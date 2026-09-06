"""Native accounting for this local experiment; never infer missing token counters."""

import json
import math

TOKEN_KEYS = (
    "inputTokens",
    "outputTokens",
    "cacheReadInputTokens",
    "cacheCreationInputTokens",
)
INPUT_KEYS = {
    "input_tokens": "inputTokens",
    "cache_read_input_tokens": "cacheReadInputTokens",
    "cache_creation_input_tokens": "cacheCreationInputTokens",
}
CORE_TOOLS = {"Bash", "Read", "Edit", "Write"}
EMPTY_RESPONSE_RETRY = (
    "[Your previous response had no visible output. Please continue and produce a "
    "user-visible response.]"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def usage_totals(models):
    require(isinstance(models, dict) and models, "Missing native model usage")
    for row in models.values():
        require(
            all(type(row.get(key)) is int and row[key] >= 0 for key in TOKEN_KEYS),
            "Missing or invalid native token counters",
        )
    totals = {key: sum(row[key] for row in models.values()) for key in TOKEN_KEYS}
    if all(
        type(row.get("thinkingTokens")) is int and row["thinkingTokens"] >= 0
        for row in models.values()
    ):
        totals["thinkingTokens"] = sum(row["thinkingTokens"] for row in models.values())
    totals["totalInputTokens"] = sum(totals[key] for key in INPUT_KEYS.values())
    totals["totalTokens"] = totals["totalInputTokens"] + totals["outputTokens"]
    return totals


def read_events(path):
    events, malformed = [], []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            event = json.loads(line)
            require(isinstance(event, dict), "Native event is not an object")
            events.append(event)
        except (ValueError, json.JSONDecodeError) as error:
            malformed.append({"line": number, "text": line, "error": str(error)})
    return events, malformed


def remember(mapping, key, value):
    require(key not in mapping or mapping[key] == value, "Conflicting native ID reuse")
    mapping[key] = value


def response_usage(message):
    usage = message.get("usage", {})
    counters = {key: usage.get(key) for key in INPUT_KEYS}
    require(
        all(type(value) is int and value >= 0 for value in counters.values()),
        "Missing per-response input counters",
    )
    return {"model": message.get("model"), "input": counters}


def collect(events):
    responses, calls, results = {}, {}, {}
    for event in events:
        message = event.get("message", {})
        if event.get("type") == "assistant":
            remember(responses, message["id"], response_usage(message))
        content = message.get("content", [])
        require(isinstance(content, list), "Unsupported native message content")
        for block in content:
            if block.get("type") == "tool_use":
                remember(calls, block["id"], block)
            elif block.get("type") == "tool_result":
                remember(results, block["tool_use_id"], block)
    return responses, calls, results


def validate_init(init, requested_model):
    require(init is not None, "Missing native init")
    require(init.get("model") == requested_model, "Unexpected primary model")
    require(
        len(init.get("tools", [])) == len(CORE_TOOLS)
        and set(init.get("tools", [])) == CORE_TOOLS,
        "Native tool set differs",
    )
    for key in ("plugins", "skills", "mcp_servers"):
        require(key in init and init[key] == [], f"Native isolation differs: {key}")


def validate_terminal_usage(terminal, totals):
    usage = terminal.get("usage", {})
    for native_key, final_key in {
        **INPUT_KEYS,
        "output_tokens": "outputTokens",
    }.items():
        value = usage.get(native_key)
        require(
            type(value) is int and value >= 0 and value == totals[final_key],
            "Terminal usage and modelUsage differ or required counter is missing",
        )


def synthetic_retries(events):
    return [
        index
        for index, event in enumerate(events)
        if event.get("type") == "user"
        and event.get("isSynthetic") is True
        and event.get("message", {}).get("content")
        == [{"type": "text", "text": EMPTY_RESPONSE_RETRY}]
        and any(row.get("type") == "assistant" for row in events[:index])
        and any(row.get("type") == "assistant" for row in events[index + 1 :])
    ]


def validate_inputs(responses, models, requested_model, events):
    require(responses, "Missing primary responses")
    for row in responses.values():
        require(row["model"] == requested_model, "Response model differs")
    remainder = {}
    for message_key, final_key in INPUT_KEYS.items():
        observed = sum(row["input"][message_key] for row in responses.values())
        remainder[message_key] = models[requested_model][final_key] - observed
    require(
        all(value >= 0 for value in remainder.values()),
        "Response inputs exceed native totals",
    )
    incomplete = any(remainder.values())
    retries = synthetic_retries(events)
    require(
        not incomplete or retries,
        "Response input totals differ without native retry evidence",
    )
    return {
        "response_input_coverage": "incomplete_native_retry"
        if incomplete
        else "complete",
        "visible_response_input_remainder": remainder,
        "primary_model_rounds_exact": not incomplete,
        "native_empty_response_retry_event_indexes": retries,
    }


def tool_timings(events, calls):
    timings = {}
    for event in events:
        metadata = event.get("tool_use_result", {})
        if not isinstance(metadata, dict):
            continue
        ids = [
            block["tool_use_id"]
            for block in event.get("message", {}).get("content", [])
            if block.get("type") == "tool_result"
        ]
        if len(ids) != 1:
            continue
        for key in ("duration_ms", "durationMs"):
            value = metadata.get(key)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                timings[ids[0]] = {
                    "milliseconds": value,
                    "source_field": f"tool_use_result.{key}",
                }
                break
    complete = bool(calls) and set(timings) == set(calls)
    return {
        "native_tool_timings": timings,
        "tool_execution_ms": sum(row["milliseconds"] for row in timings.values())
        if complete
        else None,
        "tool_timing_status": "complete_native_intervals"
        if complete
        else "partial"
        if timings
        else "not_exposed",
    }


def summarize(events, requested_model):
    """Return validated final output accounting and deduplicated response inputs."""
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
    validate_init(init, requested_model)
    require(terminal is not None, "Missing native terminal result; spend is unknown")
    models = terminal.get("modelUsage", {})
    all_tokens = usage_totals(models)
    validate_terminal_usage(terminal, all_tokens)
    require(requested_model in models, "Requested model absent from final usage")
    responses, calls, results = collect(events)
    require(set(calls) == set(results), "Native tool/result linkage incomplete")
    coverage = validate_inputs(responses, models, requested_model, events)
    cost = terminal.get("total_cost_usd")
    require(
        type(cost) in (int, float) and math.isfinite(cost) and cost >= 0,
        "Native cost is unknown",
    )
    return {
        **coverage,
        **tool_timings(events, calls),
        "reported_model": init["model"],
        "isolation_init": {
            key: init[key] for key in ("tools", "plugins", "skills", "mcp_servers")
        },
        "all_model_usage": models,
        "all_model_tokens": all_tokens,
        "primary_model_tokens": usage_totals(
            {requested_model: models[requested_model]}
        ),
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
        "output_accounting": "Final modelUsage only; per-event output snapshots are incomplete",
    }
