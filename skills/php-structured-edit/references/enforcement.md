# Enforcing AST-only PHP writes

`SKILL.md` and `AGENTS.md` state the rule, but a rule is an instruction, not a control. After the fact an identical result gives no clue whether it came from an AST transaction or from `sed` — so enforcement has to happen **before** the write.

`hooks/php-ast-only.py` in this repository is a `PreToolUse` gate that denies text mutation of PHP.

## What it blocks

| Tool | Condition |
| --- | --- |
| `Edit`, `Write`, `MultiEdit`, `NotebookEdit` | the target path ends in `.php` or `.phtml` |
| `Bash` | `sed -i` / `perl -i` on a `.php` path, a shell or script redirect into a `.php` file, `apply_patch` on a `.php` path |

Read-only shell work is untouched: `cat`, `grep`, `php -l`, `git diff` and friends never match. A command that already contains `php-ast-edit` is allowed through.

## Claude Code

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [
          {"type": "command", "command": "python3 /path/to/php-ast-edit-skill/hooks/php-ast-only.py"}
        ]
      }
    ]
  }
}
```

Put it in `~/.claude/settings.json` for every project, or in a project's `.claude/settings.json` to scope it to one repository.

## Other harnesses

The gate reads a `{"tool_name": …, "tool_input": {…}}` object on stdin and answers with a `permissionDecision` object on stdout. Any harness that can shell out before a tool call can adopt it by mapping its own tool names onto that shape; the matching logic needs no change.

Where no hook layer exists, the fallback is the CI check every reviewer can run: a diff that touches `.php` and was not produced by an AST transaction is not detectable from the result, so review the *method*, not the output.

## What it cannot catch

A shell can write a file in unboundedly many ways: `python3 -c 'open("A.php","w")…'`, `php -r 'file_put_contents(…)'`, a script that does it three call frames down. The gate matches the shapes an agent actually reaches for — the editing tools, in-place `sed`/`perl`, redirects, `tee`, `apply_patch` — and does not pretend to be a sandbox. Its job is to make the wrong move cost a round trip and name the right one, not to make it impossible.

Two consequences worth stating. It fails open: a payload it cannot parse is allowed through, because a hook that bricks the session on a malformed input is worse than one that misses a case. And it is not a security boundary — an agent that means to circumvent it can, so it belongs in the same category as a linter, not a permission system.

## The deliberate exception

`PHP_AST_ONLY_OFF=1` lets one call through. It exists for the cases where the AST is not the right instrument: a test fixture that must contain deliberately broken PHP, a generated file, a merge-conflict resolution. Reach for it explicitly and say why — not to get past a snippet that would not parse, which is the gate doing its job.
