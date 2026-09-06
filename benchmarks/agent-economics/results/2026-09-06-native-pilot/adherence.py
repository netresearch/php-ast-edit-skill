"""Derive the frozen pilot's snapshot-guard audit without executing trace commands.

Only the sequential tool and command forms observed in these six traces are
supported. Unknown or ambiguous forms fail rather than imply workflow compliance.
"""

import hashlib
import json
from dataclasses import dataclass

PAYLOAD_NAME = "edits.json"
FILE_PATH = "file_path"
IS_ERROR = "is_error"
GUARD_PRESENT = "sha256_present"
LOCAL_APPLY = f"php-ast-edit apply --input {PAYLOAD_NAME}"
HEREDOC_START = "cat > /tmp/edits.json << 'EOF'\n"
HEREDOC_END = "\nEOF\nphp-ast-edit apply --input /tmp/edits.json"
INPUT_KEYS = {
    "Read": {FILE_PATH},
    "Write": {FILE_PATH, "content"},
    "Edit": {FILE_PATH, "old_string", "new_string", "replace_all"},
    "Bash": {"command"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tool_events(events):
    for event in events:
        for block in event.get("message", {}).get("content", []):
            kind = block["type"]
            if kind == "text":
                continue
            require(kind in {"tool_use", "tool_result"}, "Unsupported message block")
            role = "assistant" if kind == "tool_use" else "user"
            require(event["type"] == role, "Unexpected tool event role")
            yield block


def completed_calls(events):
    """Reject overlap: every observed request completes before the next request."""
    pending, seen = None, set()
    for block in tool_events(events):
        if block["type"] == "tool_use":
            require(pending is None, "Unsupported overlapping tool requests")
            require(block["id"] not in seen, "Duplicate tool request ID")
            seen.add(block["id"])
            pending = block
            continue
        require(pending is not None, "Tool result precedes its request")
        require(block["tool_use_id"] == pending["id"], "Tool result ID differs")
        require(type(block.get(IS_ERROR, False)) is bool, "Invalid tool outcome")
        yield pending, block
        pending = None
    require(pending is None, "Tool result missing")


@dataclass(frozen=True)
class Payload:
    text: str
    producers: tuple


class TraceAudit:
    def __init__(self, run_id, initial_hashes):
        self.work = f"{{PILOT_ROOT}}/runs/{run_id}/work"
        self.initial_hashes = initial_hashes
        self.reads = {}
        self.payloads = {}
        self.attempts = []
        self.applied = set()

    def source_name(self, path):
        for name in self.initial_hashes:
            if path in {name, f"{self.work}/{name}"}:
                return name
        raise ValueError("Unsupported source path")

    def payload_name(self, path):
        require(
            path in {PAYLOAD_NAME, f"{self.work}/{PAYLOAD_NAME}"},
            "Unsupported payload path",
        )
        return PAYLOAD_NAME

    def read(self, call):
        name = self.source_name(call["input"][FILE_PATH])
        require(name not in self.applied, "Unsupported read after successful apply")
        self.reads[name] = call["id"]

    def write(self, call):
        values = call["input"]
        name = self.payload_name(values[FILE_PATH])
        require(isinstance(values["content"], str), "Payload content is not text")
        self.payloads[name] = Payload(values["content"], (call["id"],))

    def edit(self, call):
        values = call["input"]
        name = self.payload_name(values[FILE_PATH])
        require(name in self.payloads, "Edit has no completed payload write")
        previous = self.payloads[name]
        old, new = values["old_string"], values["new_string"]
        require(isinstance(old, str) and old != "", "Invalid edit search text")
        require(isinstance(new, str), "Invalid edit replacement text")
        require(values["replace_all"] is False, "Unsupported replacement mode")
        require(previous.text.count(old) == 1, "Ambiguous or unmatched payload edit")
        self.payloads[name] = Payload(
            previous.text.replace(old, new, 1), previous.producers + (call["id"],)
        )

    def file_entry(self, entry):
        require(isinstance(entry, dict), "Invalid payload file entry")
        require({"path", "edits"} <= set(entry), "Missing file keys")
        require(set(entry) <= {"path", "edits", "sha256"}, "Unsupported file keys")
        require(isinstance(entry["edits"], list) and entry["edits"], "Missing edits")
        require(all(isinstance(edit, dict) for edit in entry["edits"]), "Invalid edits")
        name = self.source_name(entry["path"])
        require(name in self.reads, "Apply has no completed source Read")
        require(name not in self.applied, "Unsupported repeated successful apply")
        guarded = "sha256" in entry
        if guarded:
            require(
                entry["sha256"] == self.initial_hashes[name],
                "Invalid or mismatched snapshot sha256",
            )
        return {
            "file": name,
            "prior_read_tool_id": self.reads[name],
            GUARD_PRESENT: guarded,
        }

    def apply(self, call, result, payload):
        document = json.loads(payload.text)
        require(
            isinstance(document, dict) and set(document) == {"files"},
            "Invalid payload root",
        )
        entries = document["files"]
        require(isinstance(entries, list) and entries, "Missing payload files")
        files = [self.file_entry(entry) for entry in entries]
        names = [entry["file"] for entry in files]
        require(len(names) == len(set(names)), "Duplicate payload source path")
        failed = result.get(IS_ERROR, False)
        self.attempts.append(
            {
                "apply_tool_id": call["id"],
                "payload_tool_ids": list(payload.producers),
                "tool_outcome": "error" if failed else "success",
                "files": files,
            }
        )
        if not failed:
            self.applied.update(names)

    def bash(self, call, result):
        command = call["input"]["command"]
        require(isinstance(command, str), "Bash command is not text")
        if command == LOCAL_APPLY:
            require(
                PAYLOAD_NAME in self.payloads, "Apply has no completed payload write"
            )
            self.apply(call, result, self.payloads[PAYLOAD_NAME])
        elif command.startswith(HEREDOC_START):
            require(command.endswith(HEREDOC_END), "Unsupported heredoc apply tail")
            text = command[len(HEREDOC_START) : -len(HEREDOC_END)]
            require("\nEOF\n" not in text, "Ambiguous heredoc delimiter")
            self.apply(call, result, Payload(text, (call["id"],)))
        else:
            self.cleanup(command, result)

    def cleanup(self, command, result):
        diff = f"git -C {self.work} diff"
        remove = {
            f"rm {self.work}/{PAYLOAD_NAME} && {diff}",
            f"git diff && rm {PAYLOAD_NAME}",
        }
        require(command == diff or command in remove, "Unsupported Bash command")
        require(not result.get(IS_ERROR, False), "Unsupported cleanup failure")
        if command in remove:
            require(PAYLOAD_NAME in self.payloads, "Cleanup has no payload")
            del self.payloads[PAYLOAD_NAME]

    def consume(self, call, result):
        name = call["name"]
        require(name in INPUT_KEYS, "Unsupported tool")
        keys = set(call["input"])
        allowed = INPUT_KEYS[name] | ({"description"} if name == "Bash" else set())
        require(INPUT_KEYS[name] <= keys <= allowed, "Unsupported tool input fields")
        if name == "Bash":
            self.bash(call, result)
            return
        handlers = {"Read": self.read, "Write": self.write, "Edit": self.edit}
        require(not result.get(IS_ERROR, False), "Unsupported non-Bash failure")
        handlers[name](call)


def derive_run(measured, trace_path, initial_hashes):
    """Return the complete audit row derived from native requests and results."""
    data = trace_path.read_bytes()
    events = [json.loads(line) for line in data.splitlines()]
    audit = TraceAudit(measured["run_id"], initial_hashes)
    for call, result in completed_calls(events):
        audit.consume(call, result)
    require(audit.attempts, "No observed apply requests")
    return {
        "run_id": measured["run_id"],
        "task_id": measured["task_id"],
        "assigned_variant": measured["variant"],
        "snapshot_guard_adherent": all(
            entry[GUARD_PRESENT]
            for attempt in audit.attempts
            for entry in attempt["files"]
        ),
        "native_trace": f"runs/{measured['run_id']}/native.jsonl",
        "native_trace_sha256": hashlib.sha256(data).hexdigest(),
        "apply_attempts": audit.attempts,
    }


def aggregate(rows):
    return {
        "assigned_full_skill_runs": len(rows),
        "snapshot_guard_adherent_runs": sum(
            row["snapshot_guard_adherent"] for row in rows
        ),
        "unguarded_apply_attempts": sum(
            any(not entry[GUARD_PRESENT] for entry in attempt["files"])
            for row in rows
            for attempt in row["apply_attempts"]
        ),
    }
