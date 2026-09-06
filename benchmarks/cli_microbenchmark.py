"""CLI microbenchmark; no model calls. All edits affect disposable fixtures only."""

import argparse
import datetime
import difflib
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, cwd, payload=None):
    # The local operator selects the engine/runtime; no shell is used. See TRUST.md.
    result = subprocess.run(  # NOSONAR(S8701)
        command,
        cwd=cwd,
        input=payload,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{command[0]} exited {result.returncode}: {result.stderr}")
    return result.stdout


def benchmark(args):
    binary = str(Path(args.bin).resolve())
    cli = [args.php, binary]
    php_version_id = int(run([args.php, "-r", "echo PHP_VERSION_ID;"], cwd=ROOT))
    multi_file_lint = php_version_id >= 80300
    rng = random.Random(args.seed)
    names = [f"Case{i}.php" for i in range(args.files)]
    samples = {
        name: []
        for name in [
            "single_ast",
            "single_patch_lint",
            "batch_ast",
            "batch_patch_lint",
            "separate_ast",
            "inspect",
            "contexts",
        ]
    }
    if args.include_operation_help:
        samples["contexts_operation"] = []
    output_bytes = {name: [] for name in samples}
    command_counts = {
        "single_ast": 1,
        "single_patch_lint": 2,
        "batch_ast": 1,
        "batch_patch_lint": 2 if multi_file_lint else args.files + 1,
        "separate_ast": args.files,
        "inspect": 1,
        "contexts": 1,
        "contexts_operation": 1,
    }
    with tempfile.TemporaryDirectory(prefix="php-ast-benchmark-") as temporary:
        work = Path(temporary)
        create = {
            "files": [
                {
                    "path": name,
                    "mode": "create",
                    "php": "<?php final class Example { public function amount() { return 1; } }",
                }
                for name in names
            ]
        }
        run(cli + ["apply"], cwd=work, payload=json.dumps(create))
        initial = {name: (work / name).read_bytes() for name in names}
        edits = [
            {
                "path": name,
                "sha256": hashlib.sha256(initial[name]).hexdigest(),
                "edits": [
                    {
                        "target": {"select": "method:Example::amount"},
                        "operation": "set_return_type",
                        "php": "int",
                    }
                ],
            }
            for name in names
        ]
        run(cli + ["apply"], cwd=work, payload=json.dumps({"files": edits}))
        expected = {name: (work / name).read_bytes() for name in names}
        for name in names:
            run([args.php, "-l", name], cwd=work)
            run(
                [
                    args.php,
                    "-r",
                    "require $argv[1]; if ((new Example())->amount() !== 1 || (new ReflectionMethod(Example::class, 'amount'))->getReturnType()?->getName() !== 'int') exit(1);",
                    name,
                ],
                cwd=work,
            )
        patches = {
            name: "".join(
                difflib.unified_diff(
                    initial[name].decode().splitlines(True),
                    expected[name].decode().splitlines(True),
                    fromfile=f"a/{name}",
                    tofile=f"b/{name}",
                )
            )
            for name in names
        }
        if any(not patch for patch in patches.values()):
            raise RuntimeError("Fixture produced no patch")
        offset = initial[names[0]].index(b"amount")
        for iteration in range(-args.warmups, args.repetitions):
            order = list(samples)
            # Reproducible sample scheduling, never a security token. See TRUST.md.
            rng.shuffle(order)  # NOSONAR(S2245)
            for variant in order:
                for name in names:
                    (work / name).write_bytes(
                        initial[name]
                    )  # exact fixture restoration
                started = time.perf_counter_ns()
                outputs = []
                if variant in ("single_ast", "batch_ast", "separate_ast"):
                    groups = (
                        [[edit] for edit in edits]
                        if variant == "separate_ast"
                        else [edits if variant == "batch_ast" else edits[:1]]
                    )
                    for group in groups:
                        outputs.append(
                            run(
                                cli + ["apply"],
                                cwd=work,
                                payload=json.dumps({"files": group}),
                            )
                        )
                elif variant in ("single_patch_lint", "batch_patch_lint"):
                    targets = names if variant == "batch_patch_lint" else names[:1]
                    outputs.append(
                        run(
                            ["git", "apply", "--whitespace=nowarn", "-"],
                            cwd=work,
                            payload="".join(patches[name] for name in targets),
                        )
                    )
                    lint_groups = (
                        [targets] if multi_file_lint else [[name] for name in targets]
                    )
                    for group in lint_groups:
                        outputs.append(run([args.php, "-l", *group], cwd=work))
                elif variant == "inspect":
                    outputs.append(
                        run(
                            cli
                            + ["inspect", "--file", names[0], "--offset", str(offset)],
                            cwd=work,
                        )
                    )
                elif variant == "contexts_operation":
                    outputs.append(
                        run(
                            cli + ["contexts", "--operation", "rename_variable"],
                            cwd=work,
                        )
                    )
                else:
                    outputs.append(run(cli + ["contexts"], cwd=work))
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                modified = set(
                    names
                    if variant in ("batch_ast", "batch_patch_lint", "separate_ast")
                    else names[:1]
                    if variant.startswith("single_")
                    else []
                )
                for name in names:
                    if (work / name).read_bytes() != (
                        expected[name] if name in modified else initial[name]
                    ):
                        raise RuntimeError(f"Incorrect output in {variant}: {name}")
                if iteration >= 0:
                    samples[variant].append(elapsed)
                    output_bytes[variant].append(
                        sum(len(output.encode()) for output in outputs)
                    )
    commit = run(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
    dirty = bool(run(["git", "status", "--porcelain"], cwd=ROOT).strip())
    summary = {
        name: {
            "median_ms": round(statistics.median(values), 3),
            "p95_ms": round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 3),
            "processes_per_sample": command_counts[name],
            "median_output_bytes": statistics.median(output_bytes[name]),
            "all_outputs_correct": True,
        }
        for name, values in samples.items()
    }
    return {
        "schema_version": 1,
        "kind": "cli_microbenchmark",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_commit": commit,
        "working_tree_dirty": dirty,
        "environment": {
            "source_root": str(ROOT),
            "executable_path": binary,
            "executable_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "php": run([args.php, "-v"], cwd=ROOT).splitlines()[0],
            "php_version_id": php_version_id,
            "xdebug_loaded": run(
                [args.php, "-r", "echo extension_loaded('xdebug') ? 'yes' : 'no';"],
                cwd=ROOT,
            ),
            "xdebug_modes": json.loads(
                run(
                    [
                        args.php,
                        "-r",
                        "echo json_encode(function_exists('xdebug_info') ? xdebug_info('mode') : []);",
                    ],
                    cwd=ROOT,
                )
            ),
            "parser": run(
                [
                    args.php,
                    "-r",
                    "require 'vendor/autoload.php'; echo Composer\\InstalledVersions::getPrettyVersion('nikic/php-parser');",
                ],
                cwd=ROOT,
            ),
        },
        "parameters": {
            "repetitions": args.repetitions,
            "warmups": args.warmups,
            "files": args.files,
            "seed": args.seed,
            "patch_lint_mode": "multi_file" if multi_file_lint else "per_file",
            "include_operation_help": args.include_operation_help,
        },
        "scope": "Process startup, command execution, output capture; fixture reset and independent byte oracle excluded. Patch arms include host PHP lint. No model requests or billed tokens measured.",
        "summary": summary,
        "samples_ms": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", default=str(ROOT / "bin/php-ast-edit"))
    parser.add_argument("--php", default="php")
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--files", type=int, default=10)
    parser.add_argument("--seed", type=int, default=76491)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-operation-help",
        action="store_true",
        help="Also measure contexts --operation rename_variable (requires compact operation help)",
    )
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmups < 0 or args.files < 1:
        parser.error("repetitions/files must be positive and warmups nonnegative")
    result = benchmark(args)
    # Explicit local report destination; the evaluator does not impose a sandbox.
    args.output.parent.mkdir(parents=True, exist_ok=True)  # NOSONAR(S8707)
    args.output.write_text(json.dumps(result, indent=2) + "\n")  # NOSONAR(S8707)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
