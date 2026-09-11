# Powered round: status and recovery

**Status on 2026-09-11: protocol recovered; original raw data unavailable here.**
The planned experiment is 30 repetitions of each task/arm combination, 120 candidate
processes. No powered-round savings claim is published. The historical account of
the stopped first round and the unresolved 16-versus-18 count are retained in the
[protocol](PROTOCOL.md#reconciliation-2026-09-11).

The source branch is `bench/powered-round` at `b51b196`; its commits name
[Claude session `session_01ChkDsp64UiozGQdWhsU4sp`](https://claude.ai/code/session_01ChkDsp64UiozGQdWhsU4sp)
on host `32116e`. The local recovery search found no active driver, candidate process
or matching output files. That observation does not establish the remote process
state. Do not start a replacement campaign and call it a recovered result.

The recovery attempt on 2026-09-11 could not contact that session: the supported
Claude cloud attachment was disabled for this account, and the desktop computer-use
bridge failed before connecting. No message was delivered and no replacement model
run was started. An export from the original session remains the missing input.

## Recover the existing evidence

On the original host, identify the `BENCH` path used by `drive.sh` from that session's
commands. Preserve `powered-aborted-1` separately from round 2. Record whether a
process is active before copying; obtain a stable snapshot after it stops. Do not
rerun either campaign, overwrite a result, remove a worktree or reconstruct a
missing receipt as a pass.

Export only these regular files, retaining missing files as missing:

| Source | Contents |
| --- | --- |
| `out/{C,D}{01..30}-{free,gate}.{json,err,status,oracle,diff,version}` | Native result/accounting, errors, exit and oracle status, final diff and CLI version |
| Same run IDs with `.oracle-output` | Oracle stdout/stderr, if the driver captured it |
| Same run IDs with `.untracked` | NUL-separated untracked, nonignored filenames before worktree cleanup, if captured |
| `out/done`, `out/harness.sha256` | Completion marker and harness hashes, if present |
| Explicitly identified per-run native transcript files | Copy separately under `transcripts/<run-id>.jsonl` after checking their contents and run attribution |

Do **not** archive `BENCH` wholesale: `cfg-*` contains credentials and account
configuration. Do not export `.credentials.json`, credential stores, environment
dumps, unrelated sessions, Composer caches or a complete home directory. The native
transcripts live under the isolated configuration's project history; select only
the exact files corresponding to this campaign, not their parent directories.

This example copies the allowlisted output files into a newly created staging
directory. It rejects nonregular or symlink entries and does not touch the source:

```bash
: "${BENCH:?set the existing campaign path}"
campaign_export=$(mktemp -d)
mkdir "$campaign_export/out"
for task in C D; do
  for number in $(seq -w 1 30); do
    for arm in free gate; do
      for extension in json err status oracle diff version oracle-output untracked; do
        source="$BENCH/out/$task$number-$arm.$extension"
        if [[ -L "$source" || ( -e "$source" && ! -f "$source" ) ]]; then
          echo "Unsupported evidence entry: $source" >&2; exit 1
        fi
        [[ ! -f "$source" ]] || cp -p -- "$source" "$campaign_export/out/"
      done
    done
  done
done
for marker in done harness.sha256; do
  source="$BENCH/out/$marker"
  if [[ -L "$source" || ( -e "$source" && ! -f "$source" ) ]]; then
    echo "Unsupported evidence entry: $source" >&2; exit 1
  fi
  [[ ! -f "$source" ]] || cp -p -- "$source" "$campaign_export/out/"
done
tar -C "$campaign_export" -czf "$campaign_export/evidence.tar.gz" out
sha256sum "$campaign_export/evidence.tar.gz"
```

Keep each round's archive distinct. Review selected output/transcript content before
publication. Accompany it with the original tool/subject/harness revisions, prompt
files and nonsecret dependency identities. Hashes detect later drift; they do not
authenticate the operator or establish that an unavailable test ran.

## Offline validation

```bash
python3 benchmarks/skill-invocation/powered/analyze.py --self-test
python3 benchmarks/skill-invocation/powered/test_powered.py
python3 benchmarks/skill-invocation/powered/analyze.py /path/to/recovered-campaign
```

These commands do not launch a model or execute candidate PHP. The analyzer always
accounts for all 120 slots. Missing/malformed status, result, oracle or metric data
are visible per run; unknown values are `null`, not zero. Failed candidates retain
their available counters alongside their exclusion reason. An absent `done` marker,
missing status or unexpected candidate IDs prevents aggregate metrics and inference,
so a partial export cannot silently become a smaller successful trial.

After a complete campaign is recovered, report all exclusions by task/arm and keep
the original diffs and native accounting with the summary. The greater-than-10%
failure rule and wall-time counter-test constrain the decision even when a nominal
p-value is small. A passing oracle covers that oracle's behavior and source scope;
it does not prove general semantic rename completeness.

The driver has no resume mode. `setup` requires a new `BENCH` path and `run` refuses
existing output/work directories. The tool, subject and resolver pins remain those
of the historical protocol. A future measurement using this repaired harness must
record its new harness revision before execution and preserve the earlier evidence
gap as a separate historical fact.

The repaired driver captures tracked changes against the frozen subject commit,
including staged or committed candidate edits. Its `.untracked` file records names,
not contents; ignored and untracked file contents are not preserved by this archive.
An old unstaged-only diff may be incomplete, and a missing historical inventory
cannot be inferred as empty. Review original transcripts/worktrees where available;
do not describe these files alone as a complete final-tree reconstruction.
