"""Frozen entrypoint contract and conservative pre-invocation observations."""

import json
import shlex
from collections import Counter

import pilot
from lsp import require
from postcheck_pilot import trace_blocks, trace_field

EXPERIMENT = "real-php-entrypoint-v1"
CONTRACT = (
    "For an explicitly named rename, the command accepts the intended symbol change,\n"
    "not precomputed call sites or replacement text. You may invoke it directly without\n"
    "reading source solely to locate edit coordinates. Use reads when needed to resolve\n"
    "task ambiguity or assess unsupported references. Reference completeness remains\n"
    "unknown; the verification requirements above still apply."
)
PRECALL_BOUNDARY = (
    "First Bash invocation beginning with the exact assigned rename executable shell "
    "word; calls in its native event are peers, and within-shell work is not separated"
)
MENTION_ONLY_COMMANDS = frozenset(
    ("echo", "cat", "/bin/echo", "/usr/bin/echo", "/bin/cat", "/usr/bin/cat")
)
SHELL_OPERATORS = frozenset(";&|<>()")


def unavailable(reason):
    return {
        "preceding_tool_calls": None,
        "preceding_tools": {},
        "preceding_call_ids": [],
        "peer_tool_calls": None,
        "peer_tools": {},
        "peer_call_ids": [],
        "first_invocation_id": None,
        "first_invocation_event": None,
        "subsequent_invocation_ids": [],
        "boundary": PRECALL_BOUNDARY,
        "unavailable_reason": reason,
    }


def is_invocation(block, command):
    """Recognize a deliberately small shell subset without executing any shell."""
    if block["name"] != "Bash":
        return False
    shell = block["input"].get("command")
    require(isinstance(shell, str), "Bash command is not a string")
    lexer = shlex.shlex(shell, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    words = list(lexer)
    if command not in shell and command not in words:
        return False
    require(words, "Empty assigned command")
    require(
        not any(mark in shell for mark in ("\n", "\r", "$", "`"))
        and not any(set(word) <= SHELL_OPERATORS for word in words if word),
        "Unsupported shell syntax mentioning the assigned command",
    )
    if words[0] in MENTION_ONLY_COMMANDS:
        return False
    require(
        words[0] == command,
        "Unsupported shell prefix mentioning the assigned command",
    )
    return True


def add_call(calls, index, block, events):
    require(events[index].get("type") == "assistant", "Tool use outside assistant")
    identifier = trace_field(block, "id")
    trace_field(block, "name")
    require(isinstance(block.get("input"), dict), "Tool input is not an object")
    if identifier in calls:
        require(
            same_block(calls[identifier][1], block),
            "Conflicting tool-use ID: " + identifier,
        )
    else:
        calls[identifier] = (index, block)


def same_block(left, right):
    # JSON distinguishes booleans from numbers, unlike Python container equality.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def validate_result(block):
    require(
        "is_error" not in block or isinstance(block["is_error"], bool),
        "Result is_error is not a boolean",
    )
    content = block.get("content")
    if isinstance(content, str):
        return
    require(isinstance(content, list), "Result content is not text or a block list")
    for part in content:
        require(isinstance(part, dict), "Result content block is not an object")
        kind = trace_field(part, "type")
        if kind == "text":
            require(isinstance(part.get("text"), str), "Result text is not a string")


def add_result(results, calls, index, block, events):
    require(events[index].get("type") == "user", "Tool result outside user")
    identifier = trace_field(block, "tool_use_id")
    require(identifier in calls, "Result has no observed tool_use: " + identifier)
    validate_result(block)
    if identifier in results:
        require(
            same_block(results[identifier], block),
            "Conflicting tool-result ID: " + identifier,
        )
    else:
        results[identifier] = block


def observed_calls(events):
    calls, results = {}, {}
    require(isinstance(events, list), "Events are not a list")
    for index, block in trace_blocks(events):
        if block["type"] == "tool_use":
            add_call(calls, index, block, events)
        elif block["type"] == "tool_result":
            add_result(results, calls, index, block, events)
    require(calls.keys() == results.keys(), "Observed tool use has no result")
    return calls


def observation(calls, invocations):
    first = invocations[0]
    boundary_event = calls[first][0]
    preceding = [key for key, (index, _) in calls.items() if index < boundary_event]
    peers = [
        key
        for key, (index, _) in calls.items()
        if index == boundary_event and key != first
    ]
    return {
        "preceding_tool_calls": len(preceding),
        "preceding_tools": dict(Counter(calls[key][1]["name"] for key in preceding)),
        "preceding_call_ids": preceding,
        "peer_tool_calls": len(peers),
        "peer_tools": dict(Counter(calls[key][1]["name"] for key in peers)),
        "peer_call_ids": peers,
        "first_invocation_id": first,
        "first_invocation_event": boundary_event,
        "subsequent_invocation_ids": invocations[1:],
        "boundary": PRECALL_BOUNDARY,
    }


def pre_calls(events, command):
    """Count observed preparation without classifying it as unnecessary work."""
    try:
        require(isinstance(command, str) and command, "Assigned command is invalid")
        calls = observed_calls(events)
        invocations = [
            key for key, (_, block) in calls.items() if is_invocation(block, command)
        ]
        require(invocations, "No assigned rename invocation observed")
        return observation(calls, invocations)
    except (TypeError, ValueError, KeyError) as error:
        return unavailable("Incomplete invocation observation: " + str(error))


def observe(run_dir, record):
    if record.get("accounting_error") or not record.get("native"):
        return unavailable("Native accounting unavailable; trace may be incomplete")
    try:
        events, malformed = pilot.native.read_events(run_dir / pilot.NATIVE_FILE)
        require(not malformed, "Malformed native trace")
        return pre_calls(events, str(run_dir / "rename-tool"))
    except (ValueError, TypeError, KeyError, OSError) as error:
        return unavailable(str(error))
