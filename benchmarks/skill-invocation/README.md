# Does the model reach for the skill?

Every other measurement in this repository asks whether an AST edit is cheaper than a
text edit. That question presumes the tool gets used. This one does not.

A skill reaches the model as one line in a listing: its `description`. Nothing else about
it is in context until something invokes it. If that line does not match how the request
is phrased, the skill is listed, paid for, and never called — and the run then measures
`Read` plus a column of `Edit` calls, exactly as if the skill were not installed.

That is not a hypothetical. It is what the first arm of this measurement did.

## What is held fixed

Prompt, repository, base commit, model, PATH and permission mode — the engine is on PATH
in every arm, `free` included, because an arm that could not reach the binary would be
measuring two changes at once. The arms differ in the configuration directory they run
under, and that directory holds nothing but credentials, a minimal `settings.json`, and
the skill under test. Running an arm against a personal
`~/.claude` measures that configuration — its `CLAUDE.md`, its other skills, whatever
standing instructions live there — and those dominate.

## Running it

```bash
export BENCH=/tmp/skill-invocation
export REPO=/path/to/a/real/php/repository
export BASE=<commit in that repository>

benchmarks/skill-invocation/prepare.sh free
benchmarks/skill-invocation/prepare.sh ast   skills/php-structured-edit
benchmarks/skill-invocation/prepare.sh trial /tmp/variant/php-structured-edit

PROMPT='Rename the private method getQueryBuilder() in Classes/Service/Repo.php to
queryBuilderFor(), including every call to it in that file. Change nothing else.'

for i in 1 2 3 4 5 6 7 8; do
  for arm in free ast trial; do
    benchmarks/skill-invocation/run.sh "rename$i" "$arm" "$PROMPT"
  done
done
benchmarks/skill-invocation/summarize.py "$BENCH" free ast trial --task rename \
  --oracle 'grep -q queryBuilderFor Classes/Service/Repo.php'
```

Give the task id a name and pass it to `--task`. A result file is named for its run's task
id and arm, so a second task measured in the same root sits beside the first, and without
the filter both go into one median — a rename and a three-change edit averaged together
and reported as repetitions of the same thing. The oracle belongs to the task too: it is
the check for `rename`, and running it over another task's runs excludes all of them as
work that was never done.

The oracle is not optional in practice. `summarize.py` without one reports every run that
exited cleanly, and a run that finished without doing the task is not a cheap run — it is
a wrong one that flatters its arm. The check runs in each run's own working tree and its
exit status decides; runs that fail it are excluded from the medians and counted in the
line above them, as are attempts that timed out or could not authenticate.

It is a command and its arguments, not a shell line — no pipes, substitutions or
redirection. Anything needing shell syntax goes in a script the oracle names.

The subject has to be a real repository with real checks. On a fixture the model has
nothing to verify against, skips the verification turns entirely, and the arms converge
on a number that says nothing about either.

## Reading the result

The headline is the invocation rate, not the token count. Averaging runs that called the
skill together with runs that did not hides the effect: a fast arm may simply be one
where the model went straight to `Edit`, and a slow arm one where a listed-but-unused
skill added its listing to every request for nothing.

Repetitions are not optional. Invocation is stochastic — the same description produced
both a 7-turn run that called the skill and a 22-turn run that did not. A single run per
arm cannot tell a description apart from a coin flip.
