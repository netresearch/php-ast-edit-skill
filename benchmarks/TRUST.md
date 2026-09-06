# Benchmark execution and trust boundaries

These scripts are local evaluator commands run by the benchmark operator. They do not
provide an HTTP endpoint, accept remote jobs, or enforce a shell or filesystem sandbox.
The operator chooses the executable, work directory, evaluator state, evidence files,
and output destinations. Reading and writing those destinations is part of the CLI
contract, including paths outside the repository.

## Inputs and execution

`cli_microbenchmark.py` runs the selected `--php` interpreter and `--bin` editor, plus
Git, against temporary fixtures. `agent_benchmark.py` runs PHP and the selected `--bin`
editor, then executes the repository's task oracle. Both subprocess helpers pass argv
lists without a shell. Command arguments are not interpolated into shell source. The
ability to select an executable is intentional; its provenance belongs in the retained
run configuration.

`tasks.json` and `run.schema.json` are repository-owned evaluator inputs. They are not
provided by the candidate being graded. The task oracle contains executable PHP and
the reference edits are answer keys. Keep those files and evaluator state outside the
candidate's supplied context. `prepare` also refuses nonempty workspaces and state paths
inside the task workspace. The surrounding harness must isolate candidate execution
when needed; these scripts run with the operator's operating-system permissions.

Import records and their transcript/oracle paths are operator-selected evidence. The
importer verifies hashes, task identity, record consistency, and the stated review
outcome. Hashes detect changed evidence; they do not authenticate its author, prove
model usage or billing, or make an untrusted record safe to execute. Importing records
does not execute their contents. Review evidence before publishing measurements.

## Outcome integrity

The grader rejects symlink files and directories in the evaluated source tree, which
excludes `.git` metadata. Expected PHP files must be regular files within the workspace.
Scope or lint failure skips runtime execution. This prevents a borrowed external file
from silently satisfying the expected source-file set.

A fresh completion marker is appended after the PHP oracle's assertions. Success
requires exit status zero and that exact marker at the end of stdout. A candidate that
calls `exit(0)` during `require` therefore cannot skip the assertions and receive a pass.
Self-tests cover that failure, a borrowed same-content file symlink, a directory symlink,
all eight reference outcomes, and missing required files.

These checks establish completion and ordinary source scope. They are not protection
against an adversarial PHP process, concurrent filesystem changes, or a candidate with
access to evaluator answers or state. Human review of incidental diff changes and
refusal explanations remains required. Use a separate execution boundary for untrusted
code; do not infer one from a passing oracle.

## Static-analysis decisions

The following decisions apply only to these local evaluators. Reassess them if either
script becomes a service, accepts jobs from another principal, or promises restricted
filesystem or command access.

| Code | Rule | Reviewed behavior and decision |
| --- | --- | --- |
| `agent_benchmark.load` | S2083, S8707 | Reads repository evaluator files or explicit local evidence/state paths. There is no HTTP input or restricted-root promise. Retain intended reads with rule-specific annotations. |
| `agent_benchmark.save` | S2083, S8707 | Creates the parent directory and writes the operator's selected state/report file. State deliberately lives outside the candidate workspace. Retain intended writes with rule-specific annotations. |
| `agent_benchmark.import_run`, `agent_benchmark.summarize` | S8707 | Read the selected results ledger; import also creates its parent and appends records. Retain these explicit local destinations with rule-specific annotations. |
| `agent_benchmark.invoke` | S6350 | Executes evaluator-controlled PHP arguments with `shell=False`; task PHP comes from the trusted manifest and the executable is an explicit operator choice. Retain intended execution with a rule-specific annotation. |
| `agent_benchmark.validate_schema` | S2631 | Schema patterns previously came only from the repository. Now only literal compiled SHA-1/SHA-256 patterns are supported; unknown patterns fail. No dynamic regex is compiled or suppressed. |
| `cli_microbenchmark.run` | S8701 | Runs the selected PHP/editor and fixed Git commands through argv without a shell. It does not claim to implement a shell sandbox. Retain intended execution with a rule-specific annotation. |
| `cli_microbenchmark.benchmark` | S2245 | A recorded seeded PRNG shuffles trial order for reproducibility. It generates no secrets, credentials, or security decisions. Retain the seeded generator with a rule-specific annotation. |
| `cli_microbenchmark.main` | S8707 | Creates the parent directory and writes the operator-selected `--output` report. Retain those explicit destinations with rule-specific annotations. |
| `efficiency.runner.invoke` | S6350, S8701, S8705 | Runs explicit operator/grader argv without a shell. Executable selection and ordinary command arguments are part of this local CLI contract, including repository snapshot and evaluator commands. It does not provide a restricted command service or shell sandbox. |
| `efficiency.engine_proxy.main` | S6350, S8705 | Passively records candidate engine requests and forwards their original argv to the real engine selected by the harness. Altering or filtering argument mistakes would bias the trace; source/ref guards belong to the engine. The proxy is not an OS sandbox and candidate code has the operator's permissions. |
| `efficiency.runner.create_campaign_directory` | S5443 | Creates a fresh direct child of Linux `/tmp` with one exclusive `mkdir(mode=0o700)`. Existing paths, including dangling symlinks, are refused; no parent creation or symlink resolution occurs. Direct-child placement uses `/tmp`'s sticky-directory semantics, while mode 0700 prevents other users reading campaign evidence. Offline tests cover permissive umask, existing files, dangling symlinks and nested paths. This is evidence-directory protection, not candidate isolation. |

Annotations name only the reviewed rule at each sink. They do not exclude entire files
or disable other security checks. Sonar documents this Python syntax in its
[2025.5 release notes](https://docs.sonarsource.com/sonarqube-server/2025.5/server-update-and-maintenance/release-notes).
Actual outcome-integrity defects are fixed and regression-tested, rather than covered
by these annotations.
