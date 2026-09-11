#!/usr/bin/env python3
"""Regression tests for the declaration-first ``php-ast-edit rename`` command.

The fixtures are disposable PHP projects.  They deliberately exercise the command through
its CLI boundary; direct Editor tests cannot catch discovery, option, guard, or exit-code
regressions.  The optional Phpactor case runs only when the pinned resolver is supplied by
the environment used for integration testing.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "bin/php-ast-edit"


class IntentCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="php-ast-intent-")
        self.root = pathlib.Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative: str, source: str) -> pathlib.Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def cli(
        self,
        *args: str,
        root: pathlib.Path | None = None,
        input_text: str | None = None,
    ):
        process = subprocess.run(
            [str(ENGINE), *args],
            cwd=root or self.root,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
        )
        text = process.stdout.strip() or process.stderr.strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw": text}
        return process.returncode, payload, text

    def rename(self, method: str, to: str, *options: str):
        return self.cli(
            "rename",
            "--method",
            method,
            "--to",
            to,
            "--path",
            str(self.root),
            *options,
        )

    def assert_refused(self, method: str, to: str, *options: str) -> str:
        status, payload, text = self.rename(method, to, *options)
        self.assertEqual(status, 2, payload)
        self.assertIn("raw" if "raw" in payload else "error", payload)
        return text

    @staticmethod
    def local_class(name: str, method: str = "old", opening: bool = True) -> str:
        prefix = "<?php\n" if opening else ""
        return prefix + (
            f"final class {name} {{\n"
            f"    private function {method}(): string {{ return $this->{method}(); }}\n"
            "}\n"
        )

    @classmethod
    def namespaced_class(cls, namespace: str, name: str) -> str:
        return f"<?php\nnamespace {namespace};\n" + cls.local_class(name, opening=False)

    def test_local_rename_updates_only_a_correct_receiver_and_reports_literal(self):
        path = self.write(
            "src/Local.php",
            "<?php\n"
            "final class Local {\n"
            "    private function OLD(): string {\n"
            "        $this->OLD();\n"
            "        $other->OLD();\n"
            "        return 'old';\n"
            "    }\n"
            "}\n",
        )

        status, report, _ = self.rename("local::old", "renamed", "--report", "agent")
        self.assertEqual(status, 0, report)
        source = path.read_text(encoding="utf-8")
        self.assertIn("function renamed", source)
        self.assertIn("$this->renamed()", source)
        self.assertIn("$other->OLD()", source)
        self.assertIn("return 'old'", source)
        self.assertEqual(report.get("report"), "agent")
        self.assertEqual(report.get("outcome"), "applied")

    def test_short_class_name_is_ambiguous_but_fqcn_selects_one(self):
        first = self.write("src/First.php", self.namespaced_class("First", "Worker"))
        second = self.write("src/Second.php", self.namespaced_class("Second", "Worker"))
        before = (first.read_bytes(), second.read_bytes())

        text = self.assert_refused("Worker::old", "newName")
        self.assertIn("ambiguous", text.lower())
        self.assertEqual(before, (first.read_bytes(), second.read_bytes()))

        status, report, _ = self.rename(r"First\Worker::old", "newName")
        self.assertEqual(status, 0, report)
        self.assertIn("function newName", first.read_text(encoding="utf-8"))
        self.assertIn("function old", second.read_text(encoding="utf-8"))

    def test_duplicate_fqcn_is_refused_without_partial_write(self):
        first = self.write("one.php", self.namespaced_class("Same", "Worker"))
        second = self.write("two.php", self.namespaced_class("Same", "worker"))
        before = (first.read_bytes(), second.read_bytes())
        text = self.assert_refused(r"Same\Worker::old", "newName")
        self.assertIn("ambiguous", text.lower())
        self.assertEqual(before, (first.read_bytes(), second.read_bytes()))

    def test_fqcn_inside_multi_namespace_file_is_resolved_structurally(self):
        path = self.write(
            "multi.php",
            "<?php\n"
            "namespace One { final class Shared { private function old(): void {} } }\n"
            "namespace Two { final class Shared { private function old(): void {} } }\n",
        )
        status, report, _ = self.rename(r"One\Shared::old", "newName")
        self.assertEqual(status, 0, report)
        source = path.read_text(encoding="utf-8")
        self.assertIn("class Shared { private function newName", source)
        self.assertIn(
            "namespace Two { final class Shared { private function old", source
        )

    def test_inherited_only_method_is_not_treated_as_a_declaration(self):
        path = self.write(
            "inherit.php",
            "<?php\nclass Base { public function old(): void {} }\n"
            "class Child extends Base {}\n",
        )
        before = path.read_bytes()
        text = self.assert_refused("Child::old", "newName")
        self.assertIn("declar", text.lower())
        self.assertEqual(before, path.read_bytes())

    def test_file_option_disambiguates_declarations_but_does_not_limit_local_edit(self):
        selected = self.write(
            "src/App/Worker.php", self.namespaced_class("App", "Worker")
        )
        other = self.write(
            "src/Other/Worker.php", self.namespaced_class("Other", "Worker")
        )
        status, report, _ = self.rename(
            "Worker::old", "newName", "--file", str(selected)
        )
        self.assertEqual(status, 0, report)
        self.assertIn("function newName", selected.read_text(encoding="utf-8"))
        self.assertIn("function old", other.read_text(encoding="utf-8"))

    def test_ignored_and_symlinked_php_are_not_declaration_candidates(self):
        ignored = self.write("ignored/Hidden.php", self.local_class("Hidden"))
        self.write(".gitignore", "ignored/\n")
        link = self.root / "src/Hidden.php"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(ignored)
        before = ignored.read_bytes()
        text = self.assert_refused("Hidden::old", "newName")
        self.assertIn("declar", text.lower())
        self.assertEqual(before, ignored.read_bytes())

    def test_sha256_guard_refuses_stale_declaration_snapshot(self):
        path = self.write("Guarded.php", self.local_class("Guarded"))
        status, report, _ = self.rename(
            "Guarded::old",
            "newName",
            "--sha256",
            "0" * 64,
        )
        self.assertEqual(status, 2, report)
        self.assertIn("STALE_SOURCE", json.dumps(report))
        self.assertIn("function old", path.read_text(encoding="utf-8"))

    def test_unknown_and_malformed_flags_are_refused_before_writing(self):
        path = self.write("Flags.php", self.local_class("Flags"))
        before = path.read_bytes()
        status, report, text = self.rename("Flags::old", "newName", "--typo", "value")
        self.assertEqual(status, 2, report)
        self.assertIn("typo", text)
        self.assertEqual(before, path.read_bytes())
        status, report, text = self.cli(
            "rename", "--method", "Flags::old", "--path", str(self.root)
        )
        self.assertEqual(status, 2, report)
        self.assertIn("--to", text)
        self.assertEqual(before, path.read_bytes())

    def test_dry_run_reports_without_writing(self):
        path = self.write("Dry.php", self.local_class("Dry"))
        before = path.read_bytes()
        status, report, _ = self.rename("Dry::old", "newName", "--dry-run")
        self.assertEqual(status, 0, report)
        file_report = report["files"][0]
        self.assertTrue(file_report["dryRun"])
        self.assertIn("diff", file_report)
        self.assertEqual(file_report["checkIds"], [])
        self.assertIsNone(report["checksPassed"])
        self.assertEqual(before, path.read_bytes())

    def test_failed_declared_check_keeps_edit_and_exits_one(self):
        path = self.write("Checked.php", self.local_class("Checked"))
        config = {
            "canonical": False,
            "verify": [{"scope": "project", "command": ["php", "-r", "exit(1);"]}],
        }
        (self.root / ".php-ast-edit.json").write_text(
            json.dumps(config),
            encoding="utf-8",
        )
        status, report, _ = self.rename("Checked::old", "newName")
        self.assertEqual(status, 1, report)
        self.assertFalse(report["checksPassed"])
        self.assertEqual(report["files"][0]["checkIds"], ["verify-1"])
        self.assertEqual(report["files"][0]["validation"]["checks"], "failed")
        self.assertFalse(report["verify"][0]["ok"])
        self.assertIn("function newName", path.read_text(encoding="utf-8"))

    def test_no_declared_checks_are_distinct_from_passed(self):
        path = self.write("Unchecked.php", self.local_class("Unchecked"))
        status, report, _ = self.rename(
            "Unchecked::old", "newName", "--report", "agent"
        )
        self.assertEqual(status, 0, report)
        self.assertEqual(report.get("checks"), "none_declared")
        self.assertIsNone(report.get("checksPassed"))
        self.assertIn("function newName", path.read_text(encoding="utf-8"))

    def test_raw_apply_rejects_non_boolean_project_and_mocks(self):
        path = self.write("Boolean.php", self.local_class("Boolean"))
        offset = path.read_text(encoding="utf-8").index("old")
        before = path.read_bytes()
        for key in ("project", "mocks"):
            with self.subTest(key=key):
                edit = {
                    "target": {"offset": offset},
                    "operation": "rename_method",
                    "to": "newName",
                    key: "yes",
                }
                document = {"files": [{"path": str(path), "edits": [edit]}]}
                status, report, text = self.cli(
                    "apply",
                    "--input",
                    "-",
                    input_text=json.dumps(document),
                )
                self.assertEqual(status, 2, report)
                self.assertIn("true or false", text)
                self.assertEqual(before, path.read_bytes())

    def test_nested_path_is_rejected_as_a_project_root(self):
        path = self.write("src/Nested.php", self.local_class("Nested"))
        before = path.read_bytes()
        status, report, text = self.cli(
            "rename",
            "--method",
            "Nested::old",
            "--to",
            "newName",
            "--path",
            str(self.root / "src"),
        )
        self.assertEqual(status, 2, report)
        self.assertIn("root", text.lower())
        self.assertEqual(before, path.read_bytes())

    def test_omitted_path_discovers_enclosing_project_from_nested_cwd(self):
        path = self.write("src/Cwd.php", self.local_class("Cwd"))
        status, report, _ = self.cli(
            "rename",
            "--method",
            "Cwd::old",
            "--to",
            "newName",
            "--file",
            "Cwd.php",
            root=self.root / "src",
        )
        self.assertEqual(status, 0, report)
        self.assertIn("function newName", path.read_text(encoding="utf-8"))

    def test_report_modes_are_forwarded(self):
        for mode in ("agent", "full", "compact"):
            with self.subTest(mode=mode):
                path = self.write(
                    f"Report{mode}.php", self.local_class(f"Report{mode}")
                )
                status, report, _ = self.rename(
                    f"Report{mode}::old", "newName", "--report", mode
                )
                self.assertEqual(status, 0, report)
                self.assertIn("function newName", path.read_text(encoding="utf-8"))

    def test_fixture_reference_finder_handles_ref_project_and_mocks(self):
        base = self.write(
            "src/Base.php",
            "<?php\nclass Base { public function old(): void {} }\n",
        )
        child = self.write(
            "src/Child.php",
            "<?php\nclass Child extends Base { public function old(): void {} }\n",
        )
        caller = self.write(
            "src/Caller.php",
            "<?php\nfunction run(Child $child): void { $child->old(); (new Child())->old(); }\n"
            "function mock($mock): void { $mock->method('old'); }\n",
        )
        harness_temp = tempfile.TemporaryDirectory(prefix="php-ast-intent-harness-")
        try:
            harness = pathlib.Path(harness_temp.name) / "run.php"
            harness.write_text(
                "<?php\n"
                "require_once $argv[2] . '/vendor/autoload.php';\n"
                "use Netresearch\\PhpAstEdit\\Editor;\n"
                "use Netresearch\\PhpAstEdit\\NodeLocator;\n"
                "use Netresearch\\PhpAstEdit\\ReferenceFinder;\n"
                "use PhpParser\\Node;\n"
                "use PhpParser\\NodeFinder;\n"
                "use PhpParser\\ParserFactory;\n"
                "final class FixtureFinder implements ReferenceFinder {\n"
                "    public function references(string $root, string $class, string $member): array {\n"
                "        $file = $root . '/src/Caller.php';\n"
                "        $source = file_get_contents($file);\n"
                "        $roots = (new ParserFactory())->createForHostVersion()->parse($source) ?? [];\n"
                "        $sites = [];\n"
                "        foreach ((new NodeFinder())->find($roots, static fn (Node $node): bool => $node instanceof Node\\Expr\\MethodCall && $node->name instanceof Node\\Identifier && strcasecmp($node->name->toString(), $member) === 0) as $call) {\n"
                "            $sites[] = ['file' => $file, 'start' => $call->name->getStartFilePos(), 'end' => $call->name->getEndFilePos() + 1, 'line' => $call->getStartLine()];\n"
                "        }\n"
                "        return ['references' => $sites, 'risky' => [], 'resolver' => 'fixture'];\n"
                "    }\n"
                "}\n"
                "$root = $argv[1];\n"
                "$path = $root . '/src/Base.php';\n"
                "$source = file_get_contents($path);\n"
                "$roots = (new ParserFactory())->createForHostVersion()->parse($source) ?? [];\n"
                "$location = (new NodeLocator())->locate($roots, strpos($source, 'old'), 'Stmt_ClassMethod');\n"
                "$document = ['report' => 'agent', 'files' => [['path' => $path, 'sha256' => hash('sha256', $source), 'edits' => [['operation' => 'rename_method', 'target' => ['ref' => $location->path, 'kind' => 'Stmt_ClassMethod'], 'to' => 'newName', 'project' => true, 'mocks' => true]]]]];\n"
                "echo json_encode((new Editor(new FixtureFinder()))->apply($document), JSON_THROW_ON_ERROR);\n",
                encoding="utf-8",
            )
            process = subprocess.run(
                ["php", str(harness), str(self.root), str(ROOT)],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(process.stdout)
        finally:
            harness_temp.cleanup()
        self.assertEqual(report["renames"][0]["declarations"], 2)
        self.assertEqual(report["renames"][0]["references"], 2)
        self.assertEqual(report["renames"][0]["mocksSet"], 1)
        self.assertNotIn("old", base.read_text(encoding="utf-8"))
        self.assertNotIn("old", child.read_text(encoding="utf-8"))
        caller_source = caller.read_text(encoding="utf-8")
        self.assertEqual(caller_source.count("old"), 0)
        self.assertEqual(caller_source.count("newName"), 3)

    def test_duplicate_fqcn_stops_fake_resolver_before_write_or_query(self):
        harness_temp = tempfile.TemporaryDirectory(prefix="php-ast-intent-duplicate-")
        try:
            harness = pathlib.Path(harness_temp.name) / "run.php"
            harness.write_text(
                r"""<?php
require_once $argv[2] . '/vendor/autoload.php';
use Netresearch\PhpAstEdit\Exception\EditException;
use Netresearch\PhpAstEdit\Editor;
use Netresearch\PhpAstEdit\MethodRenameCommand;
use Netresearch\PhpAstEdit\ReferenceFinder;
final class CountingFinder implements ReferenceFinder {
    public static int $queries = 0;
    public function references(string $root, string $class, string $member): array {
        ++self::$queries;
        return ['references' => [], 'risky' => [], 'resolver' => 'fixture'];
    }
}
$root = $argv[1];
$options = ['method' => 'Same\\Worker::old', 'to' => 'newName', 'path' => $root, 'file' => $root . '/two.php'];
if ($argv[3] === '1') {
    $options['mocks'] = true;
}
try {
    $document = (new MethodRenameCommand())->document($options);
    (new Editor(new CountingFinder()))->apply($document);
    echo json_encode(['status' => 0, 'queries' => CountingFinder::$queries], JSON_THROW_ON_ERROR);
} catch (EditException $failure) {
    echo json_encode(['status' => 2, 'queries' => CountingFinder::$queries, 'error' => $failure->getMessage()], JSON_THROW_ON_ERROR);
}
""",
                encoding="utf-8",
            )
            for visibility, mocks in (("public", "0"), ("private", "1")):
                with self.subTest(visibility=visibility, mocks=mocks):
                    source = (
                        "<?php\nnamespace Same;\n"
                        f"final class Worker {{ {visibility} function old(): void {{}} }}\n"
                    )
                    first = self.write("one.php", source)
                    second = self.write("two.php", source)
                    before = (first.read_bytes(), second.read_bytes())
                    process = subprocess.run(
                        ["php", str(harness), str(self.root), str(ROOT), mocks],
                        cwd=self.root,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(process.returncode, 0, process.stderr)
                    report = json.loads(process.stdout)
                    self.assertEqual(report["status"], 2, report)
                    self.assertEqual(report["queries"], 0, report)
                    self.assertIn("duplicate", report["error"].lower())
                    self.assertIn(r"Same\Worker", report["error"])
                    self.assertEqual(before, (first.read_bytes(), second.read_bytes()))
        finally:
            harness_temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
