# Experimental revision adapter

This local benchmark helper combines source reads, mandatory snapshot guards, and
compact reports around the unchanged `php-ast-edit` transaction engine. It is an
experimental interface for trusted benchmark workspaces, not a filesystem sandbox
or a production service.

It needs Python 3.10+, POSIX file locking, PHP 8.2+, and a source runtime containing
the engine and its Composer dependencies. Put this directory on `PATH` and set:

```bash
export PHP_AST_EDIT_BIN=/absolute/runtime/bin/php-ast-edit
export PHP_AST_AGENT_STATE_DIR=/absolute/run-evidence/adapter-state
```

The state directory must be outside the current candidate working directory. It
stores source snapshots, revision handles, full truncated reports, and an
append-only `audit.jsonl`. The harness must give each run its own state directory.
The adapter invokes `PHP_AST_EDIT_BIN` directly; its adjacent runtime root supplies
`vendor/autoload.php` for the read helper. Without that environment variable, it
uses this repository's engine.

## Read and apply

```bash
php-ast-agent read --mode focused --files src/Cache.php --select method:Cache::key
php-ast-agent apply <<'JSON'
{"files":[{"path":"src/Cache.php","revision":"HANDLE_FROM_READ","edits":[{"operation":"rename_variable","target":{"select":"method:Cache::key"},"from":"value","to":"input"}]}]}
JSON
```

The read response contains a fresh `revision` for each file. Pass that exact handle
in the corresponding file entry. Apply accepts the engine's existing `files` and
`edits` structure with mandatory `revision` replacing `sha256`. This experiment
supports editing or deleting existing, UTF-8 PHP files; creating files and dry-run
previews are outside its scope. Multiple files belong in one apply request to retain engine transaction
behavior. No intermediate payload file is required.

Read modes share the same revision and write path:

- `--mode full` returns the complete file, including when `--select` is present.
- `--mode focused --select method:Cache::key` returns the complete selected node,
  including attached comments and its entire body, plus namespace/import/class
  declaration context. A compact outline lists named types, functions, and methods;
  outline bodies are explicitly omitted, long signatures are marked truncated,
  and the outline is limited to 100 entries. The selected node is never truncated.
- Focused mode without a selector returns the complete file. Selecting a class
  returns the complete class body. The adapter does not infer which code matters.

Selectors use the engine's `NodeLocator` rules: `class:Cache`, `method:Cache::key`,
`function:helper`, and the other supported named declaration selectors. Missing or
ambiguous selections fail. One selector applies to every file in that read;
different selectors can be read in separate commands within one shell call.
With no explicit mode, providing a selector chooses focused mode, otherwise full.

The recorded hash comes from the exact bytes returned by the read operation.
Apply resolves each handle to that stored hash and passes it to the engine's
`sha256` guard. Unknown handles, another canonical file path, duplicate paths,
explicit `sha256`, and externally changed bytes fail before engine execution.
The engine also checks the supplied hash as part of its own transaction. The
adapter never substitutes a newly computed hash for the recorded hash.

After a successful apply, all existing handles for each affected path are
consumed, even for an unchanged result. A failed apply that actually changes bytes
(for example, a project check fails after edits are retained) also consumes those
handles. Rejected, unchanged transactions retain their handles. Read again before
another successful edit. The state lock serializes this adapter's reads and writes;
it does not prevent external editors from changing files.

## Reports and audit

The response preserves actual operation effects, formatter results, lint status,
project checks, errors, and genuine warnings. Normal `NOT_CANONICAL` output becomes
`printer_info: "not_canonical"`; it is not a correctness failure. Deprecated
`parsed`/`valid` aliases and duplicate hashes/warning text are omitted. `ok` follows
the engine exit status; a failed project check can therefore return `ok: false`
with an actual file diff and retained edits.

Diffs are computed from the stored bytes and actual post-engine files, with three
lines of context. Each visible diff is bounded to 100 lines and 12,000 UTF-8 bytes.
A shortened diff has `diff_truncated: true` and the top-level `full_diff` command
retrieves the complete stored diff, for example:

```bash
php-ast-agent diff --report REPORT_HANDLE
```

Audit entries record each successful read's mode, selector, canonical paths,
revision handles, and hashes. Every apply attempt records the supplied document
(or malformed input), followed by a result recording resolved server hashes,
engine exit status when invoked, and the compact outcome. Failures remain in the
append-only audit. State and logs contain source code and must be handled as run
evidence; their filesystem placement is not an access-control boundary.

## Local verification

```bash
python3 benchmarks/agent-economics/efficiency/adapter/test_adapter.py
```

Tests use disposable fixtures and the real engine, including source/context
completeness, stale and wrong-path guards, multi-file failure atomicity, actual
lint and failed checks, residual-rename warnings, handle invalidation, malformed
input auditing, and replay of truncated and missing-final-newline diffs. They do
not invoke candidate models.
