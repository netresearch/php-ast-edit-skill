# 2026-09-09 — the description decides whether the skill is used at all

Haiku 4.5, isolated configurations, a real TYPO3 extension that declares both a
`formatter` and a `verify` command. Method in [README.md](README.md).

## Task A — one rename

> Rename the private method `getQueryBuilder()` in
> `Classes/Service/CredentialRepository.php` to `queryBuilderFor()`, including every call
> to it in that file. Change nothing else. Make sure the project static analysis still
> passes.

One declaration, five calls. Every run that finished made the correct six replacements;
the arms differ in what that cost, not in whether it worked.

| arm | n | invoked | turns | output | cache read | usd |
| --- | --- | --- | --- | --- | --- | --- |
| no skill installed | 3 | — | 12.0 | 3013 | 534532 | 0.157 |
| description as shipped | 8 | 1/8 | 12.5 | 3414 | 563498 | 0.160 |
| intermediate wording | 8 | 4/8 | 13.0 | 3396 | 615982 | 0.168 |
| task-shaped wording | 8 | **6/8** | **9.5** | 2582 | 409938 | 0.147 |

Medians. Invocation 1/8 against 6/8 is Fisher p = 0.04. The turn difference between those
arms is not separately significant at this n; read it as what follows from invoking the
tool, not as a second result.

The shipped description names what the tool operates on — "symbols, members, types,
statements, expressions". The request says "rename the method and its call sites". Those
words are not in the description, and seven of eight runs went to `Read` plus six `Edit`
calls. Wording that lists the *tasks* rather than the *object model* moved that to six of
eight.

Per-run turn counts, `*` marking the runs that invoked the skill:

```
as shipped   18  11*  12  19  11  15  11  13
task-shaped   8*  9*  12  17  10*  8*  7*  21*
```

Invocation is stochastic either way. A single run per arm cannot tell a description apart
from a coin flip — the first pass of this measurement recorded 7 turns for the
task-shaped arm and 18 for the shipped one, and both were the tail of their own arm.

## Task B — three changes in one file

> Three changes in `Classes/Service/RateLimiterService.php`, and nothing else: rename the
> private method `buildLockoutKey()` to `lockoutKeyFor()` including every call to it; add
> a private method `clearAttempts(string $key): void` that removes `$key` from the cache
> the class already uses; and give `checkRateLimit()` the docblock […]

Each of those three is named in the task-shaped description. All three arms were run:

| arm | n | invoked | turns | output | cache read | usd |
| --- | --- | --- | --- | --- | --- | --- |
| no skill installed | 5 | — | 17.0 | 5591 | 832450 | 0.217 |
| description as shipped | 5 | 0/5 | 16.0 | 4880 | 773838 | 0.199 |
| task-shaped wording | 5 | 0/5 | 17.0 | 4624 | 828988 | 0.204 |

**Zero of ten.** Every run in both skill arms went `Read`, seven `Edit` calls, then the
project's checks — the same shape as the arm with no skill installed at all.

So the description is not the whole mechanism, and a mixed task is where it fails. The
request opens by announcing three changes; from there the model plans one read and a
column of edits, and no wording in the listing interrupts that. Whatever makes a request
read as *write this code* rather than *restructure this code* outweighs the description
entirely.

That also answers a plausible expectation the other way round: more changes per session
should amortise the one-time cost of reading the skill. Here more changes made invocation
*less* likely, not more. The Task A improvement is real and worth shipping; it is not a
general fix, and this file records that rather than letting the Task A number imply one.

## What the invoking runs still spend

From the transcripts of the Task A runs that did invoke it:

- Each spent a turn locating the executable — `which php-ast-edit || find . -name
  php-ast-edit`. `SKILL.md` opens by asking the reader to "resolve the executable once"
  and lists four places to look, while the skill ships `scripts/php-ast-edit`, a wrapper
  that resolves all four itself.
- Three wrote a JSON payload through a heredoc, although step 3 of the same file says a
  single edit against a named target needs no payload file.

Both are `SKILL.md` body problems, not description problems, and neither is measured
here. An arm that moved the flag form to the top of the body ran at n=3 and invoked the
skill once — too few to separate from the description effect, so it is not reported as a
result.
