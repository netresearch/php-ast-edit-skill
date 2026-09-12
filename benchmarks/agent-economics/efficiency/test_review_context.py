"""Offline tests for the bounded pre-command review context helper."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import review_context


class ReviewContextTests(unittest.TestCase):
    def repo(self):
        temporary = tempfile.TemporaryDirectory(prefix="php-ast-review-context-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        return root

    def stage(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        subprocess.run(["git", "add", name], cwd=root, check=True)
        return path

    def test_snapshot_is_before_write_and_kept_in_memory(self):
        root = self.repo()
        self.stage(root, "check.php", b"<?php\r\nold();\r\n")
        snapshot = review_context.capture(root, ["check.php"])
        (root / "check.php").write_bytes(b"<?php\r\nnew();\r\n")
        output = json.dumps(
            {
                "ok": True,
                "renames": [{"literals": [{"file": "check.php", "lines": [2]}]}],
            }
        ).encode()

        augmented = json.loads(review_context.augment(output, snapshot))
        entry = augmented["reviewContext"]["entries"][0]
        self.assertEqual(entry["text"], "old();")
        self.assertEqual(
            entry["sha256"], hashlib.sha256(b"<?php\r\nold();\r\n").hexdigest()
        )

    def test_literals_and_not_renamed_are_deduplicated_and_crlf_is_preserved(self):
        root = self.repo()
        self.stage(root, "check.php", b"one\r\ntarget()\r\nthree\r\n")
        snapshot = review_context.capture(root, ["check.php"])
        report = {
            "id": 7,
            "renames": [
                {
                    "literals": [
                        {"file": "check.php", "lines": [2, 2]},
                        {"file": "check.php", "lines": [2]},
                    ],
                    "notRenamed": ["check.php:2"],
                }
            ],
        }

        augmented = json.loads(
            review_context.augment(json.dumps(report).encode(), snapshot)
        )
        context = augmented["reviewContext"]
        self.assertEqual(len(context["entries"]), 1)
        self.assertEqual(context["entries"][0]["text"], "target()")
        self.assertEqual(context["omitted"], 0)

    def test_multiline_text_is_utf8_bounded_and_marked(self):
        root = self.repo()
        self.stage(root, "long.php", ("é" * 200 + "\r\nsecond\n").encode())
        snapshot = review_context.capture(root, ["long.php"])
        report = {"renames": [{"literals": [{"file": "long.php", "lines": [1]}]}]}

        context = json.loads(
            review_context.augment(json.dumps(report).encode(), snapshot)
        )["reviewContext"]
        entry = context["entries"][0]
        self.assertTrue(entry["truncated"])
        self.assertLessEqual(len(entry["text"].encode()), 240)
        entry["text"].encode().decode("utf-8")

    def test_invalid_utf8_and_nul_are_omitted(self):
        root = self.repo()
        self.stage(root, "bad.php", b"bad\xff\n")
        self.stage(root, "nul.php", b"has\x00nul\n")
        snapshot = review_context.capture(root, ["bad.php", "nul.php"])
        report = {
            "renames": [
                {
                    "literals": [
                        {"file": "bad.php", "lines": [1]},
                        {"file": "nul.php", "lines": [1]},
                    ]
                }
            ]
        }

        context = json.loads(
            review_context.augment(json.dumps(report).encode(), snapshot)
        )["reviewContext"]
        self.assertEqual(context["entries"], [])
        self.assertEqual(context["omitted"], 2)

    def test_unsafe_snapshot_paths_and_symlinks_are_rejected(self):
        root = self.repo()
        outside = root.parent / "outside-review-context.txt"
        outside.write_text("outside")
        self.addCleanup(outside.unlink)
        link = root / "link.php"
        link.symlink_to(outside)
        subprocess.run(["git", "add", "link.php"], cwd=root, check=True)
        with self.assertRaises(review_context.SnapshotError):
            review_context.capture(root, ["link.php"])

        with (
            patch.object(
                review_context.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["git"], 0, stdout=b"../outside-review-context.txt\x00", stderr=b""
                ),
            ),
            self.assertRaises(review_context.SnapshotError),
        ):
            review_context.capture(root, ["../outside-review-context.txt"])

    def test_snapshot_bounds_are_hard_errors(self):
        root = self.repo()
        names = [f"f{i}" for i in range(201)]
        for name in names:
            (root / name).write_bytes(b"x")
        with (
            patch.object(
                review_context.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["git"],
                    0,
                    stdout=b"\x00".join(name.encode() for name in names) + b"\x00",
                    stderr=b"",
                ),
            ),
            self.assertRaisesRegex(review_context.SnapshotError, "200"),
        ):
            review_context.capture(root, names)

        huge = b"x" * (review_context.MAX_FILE_BYTES + 1)
        self.stage(root, "huge.php", huge)
        with self.assertRaisesRegex(review_context.SnapshotError, "bytes"):
            review_context.capture(root, ["huge.php"])

        total_names = [f"total{i}" for i in range(5)]
        for name in total_names:
            (root / name).write_bytes(b"x" * review_context.MAX_FILE_BYTES)
        with (
            patch.object(
                review_context.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["git"],
                    0,
                    stdout=b"\x00".join(name.encode() for name in total_names)
                    + b"\x00",
                    stderr=b"",
                ),
            ),
            self.assertRaisesRegex(review_context.SnapshotError, "4194304"),
        ):
            review_context.capture(root, total_names)

    def test_malformed_or_inapplicable_reports_are_byte_for_byte_unchanged(self):
        root = self.repo()
        self.stage(root, "check.php", b"target\n")
        snapshot = review_context.capture(root, ["check.php"])
        for output in (
            b"not json",
            b'{"ok":true}',
            b'{"renames":[]}',
            b'{"renames":[{}]}',
        ):
            self.assertIs(review_context.augment(output, snapshot), output)

    def test_old_report_values_survive_and_context_has_whole_result_limit(self):
        root = self.repo()
        for index in range(25):
            self.stage(root, f"f{index}.php", f"value {index}\n".encode())
        snapshot = review_context.capture(
            root, [f"f{index}.php" for index in range(25)]
        )
        report = {
            "number": 1.5,
            "flag": False,
            "renames": [{"notRenamed": [f"f{index}.php:1" for index in range(25)]}],
        }
        augmented = json.loads(
            review_context.augment(json.dumps(report).encode(), snapshot)
        )
        self.assertEqual(augmented["number"], report["number"])
        self.assertEqual(augmented["flag"], report["flag"])
        context = augmented["reviewContext"]
        self.assertLessEqual(
            len(
                json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode()
            ),
            8192,
        )
        self.assertLessEqual(len(context["entries"]), 20)
        self.assertGreaterEqual(context["omitted"], 5)

    def test_unallowlisted_report_path_is_omitted_and_original_bytes_remain(self):
        root = self.repo()
        self.stage(root, "check.php", b"target\n")
        snapshot = review_context.capture(root, ["check.php"])
        output = b'{"ok":true,"renames":[{"notRenamed":["candidate.php:1"]}]}\n'

        augmented = review_context.augment(output, snapshot)
        self.assertTrue(augmented.startswith(output[:-2]))
        context = json.loads(augmented)["reviewContext"]
        self.assertEqual(context["entries"], [])
        self.assertEqual(context["omitted"], 1)

    def test_git_listing_runs_once_for_multiple_or_no_allowlisted_files(self):
        root = self.repo()
        self.stage(root, "first.txt", b"first\n")
        self.stage(root, "second.txt", b"second\n")
        for names in (["first.txt", "second.txt"], []):
            with (
                self.subTest(names=names),
                patch.object(
                    review_context.subprocess, "run", wraps=subprocess.run
                ) as execute,
            ):
                snapshot = review_context.capture(root, names)
                self.assertEqual(execute.call_count, 1)
                self.assertEqual(list(snapshot.files), names)


if __name__ == "__main__":
    unittest.main()
