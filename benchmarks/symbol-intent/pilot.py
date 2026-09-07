#!/usr/bin/env python3
"""Prepare/run the prospective synthetic pilot. Preparation never calls a model."""

import argparse
import hashlib
import json
import os
import random
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
sys.path.insert(0, str(SOURCE / "benchmarks/agent-economics/efficiency"))
import native
from lsp import CONFIG, PHAR_SHA256, require
from test_symbol_intent import fixture

MODEL = "claude-haiku-4-5-20251001"
ARMS = ("text", "intent", "phpactor")
COMMON = """Complete the requested PHP change efficiently and correctly. You may batch
reads, searches, shell scripts, edits and checks in one tool call. Preserve unrelated
behavior, comments and literal strings. Inspect enough code to establish the scope.
Work only in the current workspace. Do not read home instructions, controller,
evaluator, state or answer files. Only invoke the assigned external command as
documented; do not inspect its implementation. Existing Bash/Read/Edit/Write tools
are available. Finish with a short factual statement of what changed and what was
checked. Do not run git commit or modify Git configuration.
"""
AST_ORACLE = r"""require $argv[1];
function shape($v) { if ($v instanceof PhpParser\Node) { $r=['type'=>$v->getType()]; foreach ($v->getSubNodeNames() as $k) {$r[$k]=shape($v->$k);} return $r; } if (is_array($v)) {return array_map('shape',$v);} return $v; }
$p=(new PhpParser\ParserFactory())->createForNewestSupportedVersion();
$result=[]; foreach (json_decode(stream_get_contents(STDIN),true) as $name=>$source) {$result[$name]=shape($p->parse($source));} echo json_encode($result,JSON_THROW_ON_ERROR);"""
RUNTIME_ORACLE = r"""foreach (glob($argv[1].'/*.php') as $p) {require $p;}
if (!method_exists(Example\Provider::class,'load') || method_exists(Example\Provider::class,'fetch') || !method_exists(Example\Other::class,'fetch')) {exit(1);}
for ($i=0;$i<(int)$argv[2]-1;$i++) {$f='Example\\run'.$i;if($f(new Example\Provider(),new Example\Other())!==[11,22]){exit(1);}} echo 'ORACLE_OK';"""


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(argv, cwd=None, **kwargs):
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=True, **kwargs
    )


def environment():
    env = os.environ.copy()
    env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def manifest(root):
    return {
        str(p.relative_to(root)): sha(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def prepare(args):
    require(
        not invoke(["git", "status", "--porcelain"], SOURCE).stdout,
        "Commit source before preparation",
    )
    phar = args.phpactor.resolve(strict=True)
    require(sha(phar) == PHAR_SHA256, "Wrong pinned Phpactor PHAR")
    output = args.output.resolve()
    output.mkdir()
    source = output / "source"
    source.mkdir()
    archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=SOURCE)
    subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
    shutil.copytree(SOURCE / "vendor", source / "vendor")
    shutil.copyfile(phar, output / "phpactor.phar")
    source_commit = invoke(["git", "rev-parse", "HEAD"], SOURCE).stdout.strip()
    blocks = [(size, repeat) for size in (2, 10, 50) for repeat in range(3)]
    random.Random(20260907).shuffle(blocks)
    schedule = []
    for block, (size, repeat) in enumerate(blocks):
        rotation = block % 3
        for arm in ARMS[rotation:] + ARMS[:rotation]:
            number = len(schedule) + 1
            run = output / f"run{number:03d}"
            run.mkdir()
            work = run / "work"
            expected = fixture(work, size)
            save(run / "expected.json", expected)
            save(run / "initial.json", manifest(work))
            invoke(["git", "init", "-q"], work, env=environment())
            invoke(["git", "add", "--", "*.php"], work, env=environment())
            invoke(
                [
                    "git",
                    "-c",
                    "user.name=Benchmark",
                    "-c",
                    "user.email=benchmark@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-qm",
                    "Initial fixture",
                ],
                work,
                env=environment(),
            )
            state = run / "state"
            state.mkdir()
            command = run / "rename-tool"
            if arm == "intent":
                argv = [
                    "python3",
                    str(source / "benchmarks/symbol-intent/symbol_intent.py"),
                    "rename_method",
                    "--root",
                    str(work),
                    "--state",
                    str(state),
                    "--phpactor",
                    str(output / "phpactor.phar"),
                ]
                command.write_text(
                    "#!/usr/bin/env python3\nimport os,sys\nos.execvp('python3', "
                    + repr(argv)
                    + " + sys.argv[1:])\n"
                )
                instruction = f"Use the experimental symbol-aware AST command for this rename: {shlex.quote(str(command))} --file Provider.php --select 'method:Provider::fetch' --to load. It resolves references, applies one guarded transaction and reports validation; completeness is unknown. It retains edits on verification failure (exit 1)."
            elif arm == "phpactor":
                command.write_text(
                    "#!/usr/bin/env python3\nimport argparse,json,subprocess,sys\nfrom pathlib import Path\nsys.path.insert(0,"
                    + repr(str(source / "benchmarks/symbol-intent"))
                    + ")\nfrom lsp import isolated_environment\np=argparse.ArgumentParser();p.add_argument('--class',dest='owner',required=True);p.add_argument('--from',dest='old',required=True);p.add_argument('--to',required=True);a=p.parse_args()\nenv=isolated_environment(Path("
                    + repr(str(state))
                    + "))\ncommon="
                    + repr(
                        [
                            "--working-dir",
                            str(work),
                            "--config-extra",
                            json.dumps(CONFIG),
                            "-n",
                        ]
                    )
                    + "\nfor operation in [['index:build'],['references:member',a.owner,a.old,'--type=method','--replace='+a.to,'--filesystem=simple']]:\n r=subprocess.run(['php',"
                    + repr(str(output / "phpactor.phar"))
                    + ",*operation,*common],env=env)\n if r.returncode: sys.exit(r.returncode)\n"
                )
                instruction = f"Use the existing Phpactor CLI route for this rename: {shlex.quote(str(command))} --class 'Example\\Provider' --from fetch --to load. It runs index:build and references:member --replace with an isolated fresh index. Completeness is unknown; it has no transaction or integrated validation. You may redirect verbose output."
            else:
                instruction = "Use ordinary text edits or a batched script for this rename. No AST or semantic refactoring tools are provided for this arm."
            if command.exists():
                command.chmod(0o755)
            prompt = f"Rename Example\\Provider::fetch to load in Provider.php and all its PHP callers in this workspace ({size} PHP files). Preserve Other::fetch, its callers and unrelated fetch text.\n\n{instruction}"
            (run / "system.txt").write_text(COMMON)
            (run / "prompt.txt").write_text(prompt)
            frozen = {
                name: sha(run / name)
                for name in (
                    "expected.json",
                    "initial.json",
                    "system.txt",
                    "prompt.txt",
                )
            }
            if command.exists():
                frozen["rename-tool"] = sha(command)
            schedule.append(
                {
                    "id": run.name,
                    "size": size,
                    "repetition": repeat,
                    "arm": arm,
                    "frozen": frozen,
                }
            )
    config = {
        "source_commit": source_commit,
        "source_manifest": manifest(source),
        "phpactor_sha256": sha(output / "phpactor.phar"),
        "model": MODEL,
        "cli": shutil.which("claude"),
        "cli_version": invoke(["claude", "--version"]).stdout.strip(),
        "schedule": schedule,
        "max_run_usd": 0.5,
        "campaign_usd": 4.0,
        "timeout_seconds": 120,
    }
    save(output / "config.json", config)
    (output / "config.sha256").write_text(sha(output / "config.json") + "\n")
    print(
        json.dumps(
            {
                "prepared": str(output),
                "source_commit": source_commit,
                "candidates": len(schedule),
                "model_calls": 0,
            }
        )
    )


def validate(output, config, row=None):
    require(
        sha(output / "config.json") == (output / "config.sha256").read_text().strip(),
        "Config changed",
    )
    require(
        manifest(output / "source") == config["source_manifest"],
        "Frozen source or dependency drift",
    )
    require(
        sha(output / "phpactor.phar") == config["phpactor_sha256"], "Resolver drift"
    )
    if row:
        run = output / row["id"]
        require(
            all(sha(run / name) == value for name, value in row["frozen"].items()),
            "Run input drift",
        )


def grade(output, run, size):
    work = run / "work"
    expected = json.loads((run / "expected.json").read_text())
    actual = {
        str(p.relative_to(work)): p.read_text()
        for p in sorted(work.rglob("*.php"))
        if ".git" not in p.parts
    }
    scope = {
        str(p.relative_to(work))
        for p in work.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }
    result = {
        "file_scope": scope == set(expected),
        "exact_bytes": actual == expected,
        "structural_correct": False,
        "runtime_correct": False,
    }
    try:
        argv = ["php", "-r", AST_ORACLE, str(output / "source/vendor/autoload.php")]
        before = json.loads(invoke(argv, input=json.dumps(expected)).stdout)
        after = json.loads(invoke(argv, input=json.dumps(actual)).stdout)
        result["structural_correct"] = before == after
        runtime = invoke(
            ["php", "-r", RUNTIME_ORACLE, str(work), str(size)], timeout=10
        )
        result["runtime_correct"] = runtime.stdout == "ORACLE_OK"
    except (subprocess.SubprocessError, ValueError) as error:
        result["error"] = str(error)
    result["success"] = all(
        result[key] for key in ("file_scope", "structural_correct", "runtime_correct")
    )
    return result


def capture(argv, run, deadline):
    started = time.monotonic()
    timed_out = False
    with (run / "native.jsonl").open("xb") as out, (run / "stderr.txt").open(
        "xb"
    ) as err:
        process = subprocess.Popen(
            argv,
            cwd=run / "work",
            env=environment(),
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        try:
            process.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    return {
        "process_exit": process.returncode,
        "timed_out": timed_out,
        "wall_time_ms": (time.monotonic() - started) * 1000,
    }


def run_pilot(args):
    require(args.execute_models, "Run requires --execute-models")
    output = args.output.resolve(strict=True)
    config = json.loads((output / "config.json").read_text())
    validate(output, config)
    require(
        invoke([config["cli"], "--version"]).stdout.strip() == config["cli_version"],
        "CLI version drift",
    )
    spent = 0.0
    # A single-use campaign: interrupted runs remain evidence, never silently resumed.
    with (output / "started.json").open("x") as marker:
        json.dump(
            {"started_unix": time.time(), "config_sha256": sha(output / "config.json")},
            marker,
        )
    for row in config["schedule"]:
        require(
            spent + config["max_run_usd"] <= config["campaign_usd"],
            "Planning allowance exhausted",
        )
        validate(output, config, row)
        run = output / row["id"]
        work = run / "work"
        initial = json.loads((run / "initial.json").read_text())
        require(
            all(sha(work / name) == value for name, value in initial.items()),
            "Fixture drift",
        )
        require(
            not invoke(
                ["git", "status", "--porcelain"], work, env=environment()
            ).stdout,
            "Dirty fixture",
        )
        argv = [
            config["cli"],
            "-p",
            "--safe-mode",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--setting-sources",
            "",
            "--settings",
            "{}",
            "--no-session-persistence",
            "--tools",
            "Bash,Read,Edit,Write",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--prompt-suggestions",
            "false",
            "--model",
            config["model"],
            "--max-budget-usd",
            str(config["max_run_usd"]),
            "--append-system-prompt",
            (run / "system.txt").read_text(),
            (run / "prompt.txt").read_text(),
        ]
        save(run / "argv.json", argv)
        measurement = {
            **row,
            "config_sha256": sha(output / "config.json"),
            **capture(argv, run, config["timeout_seconds"]),
        }
        measurement["oracle"] = grade(output, run, row["size"])
        (run / "diff.patch").write_text(
            invoke(
                ["git", "diff", "--no-ext-diff", "HEAD"], work, env=environment()
            ).stdout
        )
        save(
            run / "final.json",
            {
                str(p.relative_to(work)): sha(p)
                for p in work.rglob("*")
                if p.is_file() and ".git" not in p.parts
            },
        )
        try:
            events, malformed = native.read_events(run / "native.jsonl")
            require(not malformed, "Malformed native trace")
            measurement["native"] = native.summarize(events, config["model"])
            validate(output, config, row)
        except ValueError as error:
            measurement["accounting_error"] = str(error)
        save(run / "measurement.json", measurement)
        print(
            json.dumps(
                {
                    "id": row["id"],
                    "arm": row["arm"],
                    "files": row["size"],
                    "success": measurement["oracle"]["success"],
                    "native": {
                        key: measurement.get("native", {}).get(key)
                        for key in (
                            "all_model_tokens",
                            "tool_calls",
                            "native_list_price_usd",
                        )
                    },
                    "wall_time_ms": measurement["wall_time_ms"],
                    "error": measurement.get("accounting_error"),
                }
            ),
            flush=True,
        )
        require(
            not measurement["timed_out"] and not measurement.get("accounting_error"),
            "Stopped on timeout/accounting/source error",
        )
        cost = measurement["native"]["native_list_price_usd"]
        require(cost <= config["max_run_usd"], "Observed run cap overrun")
        spent += cost
    save(
        output / "complete.json",
        {"attempts": len(config["schedule"]), "native_list_price_usd": spent},
    )


def summarize(args):
    output = args.output.resolve(strict=True)
    records = [
        json.loads(path.read_text())
        for path in sorted(output.glob("run*/measurement.json"))
    ]
    rows = []
    for size in (2, 10, 50):
        for arm in ARMS:
            group = [r for r in records if r["size"] == size and r["arm"] == arm]
            if not group:
                continue
            known = [
                r for r in group if "native" in r and not r.get("accounting_error")
            ]
            row = {
                "size": size,
                "arm": arm,
                "attempts": len(group),
                "successes": sum(r["oracle"]["success"] for r in group),
                "known_usage": len(known),
            }
            for key, values in {
                "tokens": [
                    r["native"]["all_model_tokens"]["totalTokens"] for r in known
                ],
                "calls": [r["native"]["tool_calls"] for r in known],
                "wall_ms": [r["wall_time_ms"] for r in group],
            }.items():
                row["median_" + key] = statistics.median(values) if values else None
                row[key] = values
            rows.append(row)
    print(json.dumps(rows, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("prepare", "run", "summarize"):
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--phpactor", type=Path, required=True)
        elif name == "run":
            command.add_argument("--execute-models", action="store_true")
    args = parser.parse_args()
    {"prepare": prepare, "run": run_pilot, "summarize": summarize}[args.action](args)


if __name__ == "__main__":
    main()
