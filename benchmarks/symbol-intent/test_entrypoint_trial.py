"""Offline negative controls for the pre-invocation trace boundary."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import entrypoint_trial as study
import pilot

COMMAND = "/campaign/run001/rename-tool"


def event(role, *blocks):
    return {"type": role, "message": {"content": list(blocks)}}


def call(identifier, name="Bash", **arguments):
    return {"type": "tool_use", "id": identifier, "name": name, "input": arguments}


def result(identifier, *, error=False):
    return {
        "type": "tool_result",
        "tool_use_id": identifier,
        "content": '{"ok": false}' if error else '{"ok": true}',
        "is_error": error,
    }


def trace(*calls):
    events = []
    for block in calls:
        events.extend((event("assistant", block), event("user", result(block["id"]))))
    return events


class EntrypointTests(unittest.TestCase):
    def assert_unknown(self, events, reason=None):
        observed = study.pre_calls(events, COMMAND)
        self.assertIsNone(observed["preceding_tool_calls"])
        self.assertIsNone(observed["peer_tool_calls"])
        self.assertEqual({}, observed["peer_tools"])
        self.assertIsNone(observed["first_invocation_id"])
        self.assertEqual([], observed["preceding_call_ids"])
        self.assertEqual(study.PRECALL_BOUNDARY, observed["boundary"])
        self.assertTrue(observed["unavailable_reason"])
        if reason:
            self.assertIn(reason, observed["unavailable_reason"])

    def test_contract_matches_prospective_paragraph_exactly(self):
        protocol = Path(__file__).with_name("ENTRYPOINT_PROTOCOL.md").read_text()
        paragraph = "\n".join(
            line.removeprefix("> ")
            for line in protocol.splitlines()
            if line.startswith("> ")
        )
        self.assertEqual(paragraph, study.CONTRACT)
        self.assertEqual("real-php-entrypoint-v1", study.EXPERIMENT)

    def test_exact_quoted_command_counts_reads_but_not_path_mentions(self):
        events = trace(
            call("source", "Read", file_path="Source.php"),
            call("listing", command="find . -name '*.php' | head -20"),
            call("echo", command=f"echo '{COMMAND}'"),
            call("cat", command=f'cat "{COMMAND}"'),
            call("rename", command=f"'{COMMAND}' --file A.php --to fetch"),
            call("later", "Read", file_path="A.php"),
        )
        observed = study.pre_calls(events, COMMAND)
        self.assertEqual(4, observed["preceding_tool_calls"])
        self.assertEqual({"Read": 1, "Bash": 3}, observed["preceding_tools"])
        self.assertEqual(
            ["source", "listing", "echo", "cat"], observed["preceding_call_ids"]
        )
        self.assertEqual("rename", observed["first_invocation_id"])
        self.assertEqual(8, observed["first_invocation_event"])
        self.assertEqual(0, observed["peer_tool_calls"])
        self.assertNotIn("unavailable_reason", observed)

    def test_quotes_preserve_an_executable_path_containing_spaces(self):
        command = "/campaign with spaces/run001/rename-tool"
        for shell in (f"'{command}' --to fetch", f'"{command}" --to fetch'):
            with self.subTest(shell=shell):
                observed = study.pre_calls(
                    trace(call("rename", command=shell)), command
                )
                self.assertEqual(0, observed["preceding_tool_calls"])

    def test_peers_are_not_pre_calls_regardless_of_block_position(self):
        events = [
            event("assistant", call("before", "Read", file_path="A.php")),
            event("user", result("before")),
            event(
                "assistant",
                call("left", "Read", file_path="A.php"),
                call("rename", command=COMMAND),
                call("right", command="pwd"),
                call("another-rename", command=COMMAND),
            ),
            event(
                "user",
                *(result(key) for key in ("left", "rename", "right", "another-rename")),
            ),
        ]
        observed = study.pre_calls(events, COMMAND)
        self.assertEqual(["before"], observed["preceding_call_ids"])
        self.assertEqual(3, observed["peer_tool_calls"])
        self.assertEqual({"Read": 1, "Bash": 2}, observed["peer_tools"])
        self.assertEqual(["left", "right", "another-rename"], observed["peer_call_ids"])
        self.assertEqual(["another-rename"], observed["subsequent_invocation_ids"])
        self.assertEqual(2, observed["first_invocation_event"])

    def test_repeated_stream_blocks_do_not_move_boundary_or_add_calls(self):
        earlier = call("read", "Read", file_path="A.php")
        rename = call("rename", command=COMMAND)
        events = trace(earlier, rename)
        events.extend(
            [
                event("assistant", copy.deepcopy(earlier), copy.deepcopy(rename)),
                event("user", result("read"), result("rename")),
            ]
        )
        observed = study.pre_calls(events, COMMAND)
        self.assertEqual(1, observed["preceding_tool_calls"])
        self.assertEqual(2, observed["first_invocation_event"])
        self.assertEqual([], observed["subsequent_invocation_ids"])

    def test_first_failed_invocation_remains_boundary_when_retry_succeeds(self):
        events = [
            event("assistant", call("first", command=COMMAND)),
            event("user", result("first", error=True)),
            event("assistant", call("recovery", "Read", file_path="A.php")),
            event("user", result("recovery")),
            event("assistant", call("retry", command=COMMAND)),
            event("user", result("retry")),
        ]
        observed = study.pre_calls(events, COMMAND)
        self.assertEqual(0, observed["preceding_tool_calls"])
        self.assertEqual("first", observed["first_invocation_id"])
        self.assertEqual(["retry"], observed["subsequent_invocation_ids"])

    def test_missing_invocation_is_unknown_not_zero(self):
        for events in ([], trace(call("mention", command=f"echo {COMMAND}"))):
            self.assert_unknown(events, "No assigned rename invocation")

    def test_shell_prefixes_operators_and_substitution_are_unknown(self):
        shells = (
            f"env {COMMAND}",
            f"X=1 {COMMAND}",
            f"command {COMMAND}",
            f"bash -c '{COMMAND}'",
            f"cd /campaign && {COMMAND}",
            f"{COMMAND}; pwd",
            f"{COMMAND} | cat",
            f"{COMMAND} > output.json",
            f"{COMMAND} &",
            f"({COMMAND})",
            f"{COMMAND}\npwd",
            f"echo $({COMMAND})",
            f"echo `{COMMAND}`",
            f"echo $NAME {COMMAND}",
            f"cat <({COMMAND})",
        )
        for shell in shells:
            with self.subTest(shell=shell):
                self.assert_unknown(
                    trace(call("unsupported", command=shell)), "Unsupported shell"
                )

    def test_unsupported_later_invocation_does_not_leave_a_known_observation(self):
        self.assert_unknown(
            trace(
                call("first", command=COMMAND),
                call("complex", command=f"true && {COMMAND}"),
            ),
            "Unsupported shell",
        )

    def test_conflicting_call_or_result_duplicates_fail_closed(self):
        cases = []
        changed_call = trace(call("rename", command=COMMAND))
        changed_call.append(
            event("assistant", call("rename", command=COMMAND + " --to other"))
        )
        cases.append((changed_call, "Conflicting tool-use"))
        changed_name = trace(call("rename", command=COMMAND))
        changed_name.append(
            event("assistant", call("rename", "Read", file_path=COMMAND))
        )
        cases.append((changed_name, "Conflicting tool-use"))
        changed_result = trace(call("rename", command=COMMAND))
        changed_result.append(event("user", result("rename", error=True)))
        cases.append((changed_result, "Conflicting tool-result"))
        changed_type = trace(call("rename", command=COMMAND, timeout=1))
        changed_type.append(
            event("assistant", call("rename", command=COMMAND, timeout=True))
        )
        cases.append((changed_type, "Conflicting tool-use"))
        for events, reason in cases:
            with self.subTest(reason=reason):
                self.assert_unknown(events, reason)

    def test_orphan_result_missing_result_and_wrong_role_fail_closed(self):
        cases = (
            ([event("user", result("rename"))], "no observed tool_use"),
            ([event("assistant", call("rename", command=COMMAND))], "has no result"),
            ([event("user", call("rename", command=COMMAND))], "outside assistant"),
            (
                [event("assistant", call("rename", command=COMMAND), result("rename"))],
                "outside user",
            ),
        )
        for events, reason in cases:
            with self.subTest(reason=reason):
                self.assert_unknown(events, reason)

    def test_malformed_events_calls_and_results_fail_closed(self):
        cases = [
            None,
            {},
            [None],
            [{"type": "assistant"}],
            [{"type": "assistant", "message": []}],
            [{"type": "assistant", "message": {"content": "bad"}}],
            [event("assistant", None)],
            [event("assistant", {"type": []})],
        ]
        for location, key, value in (
            (0, "id", None),
            (0, "name", 7),
            (0, "input", []),
            (0, "input", {"command": None}),
            (1, "tool_use_id", []),
            (1, "content", None),
            (1, "content", [None]),
            (1, "content", [{"type": "text", "text": 7}]),
            (1, "is_error", "false"),
        ):
            events = trace(call("rename", command=COMMAND))
            events[location]["message"]["content"][0][key] = value
            cases.append(events)
        cases.append(trace(call("rename", command="'" + COMMAND)))
        for events in cases:
            with self.subTest(events=events):
                self.assert_unknown(events)

    def test_non_bash_path_mention_is_a_read_not_an_invocation(self):
        self.assert_unknown(
            trace(call("read", "Read", file_path=COMMAND)), "No assigned rename"
        )

    def test_observe_requires_accounting_and_uses_the_native_trace_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            events = trace(call("rename", command=str(run_dir / "rename-tool")))
            with patch.object(
                pilot.native, "read_events", return_value=(events, [])
            ) as read:
                for record in (
                    {},
                    {"native": {}},
                    {"native": {"ok": True}, "accounting_error": "bad"},
                ):
                    self.assertIsNone(
                        study.observe(run_dir, record)["preceding_tool_calls"]
                    )
                read.assert_not_called()
                observed = study.observe(run_dir, {"native": {"ok": True}})
                self.assertEqual(0, observed["preceding_tool_calls"])
                read.assert_called_once_with(run_dir / pilot.NATIVE_FILE)

    def test_observe_reads_valid_jsonl_and_retains_unknown_for_bad_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            path = run_dir / pilot.NATIVE_FILE
            record = {"native": {"ok": True}}
            self.assertIsNone(study.observe(run_dir, record)["preceding_tool_calls"])
            events = trace(call("rename", command=str(run_dir / "rename-tool")))
            path.write_text("\n".join(json.dumps(row) for row in events) + "\n")
            self.assertEqual(0, study.observe(run_dir, record)["preceding_tool_calls"])
            with path.open("a") as handle:
                handle.write("malformed capture\n")
            self.assertIsNone(study.observe(run_dir, record)["preceding_tool_calls"])


if __name__ == "__main__":
    unittest.main()
