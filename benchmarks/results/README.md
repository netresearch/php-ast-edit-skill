# Recorded measurements

CLI microbenchmark JSON files in this directory contain raw timings and the exact source
commit/environment reported by the runner. Reproduce them with the command in the
[parent guide](../README.md).

The initial review of v0.7.0 found that batching reduced local CLI startup overhead while
a small single AST edit took longer than a contextual patch plus lint. Those historical
observations are not a performance claim for the current implementation: it adds checks
that change runtime cost. Use a sample from the version you intend to deploy.

There are no completed model A/B results in this directory. Agent tasks and their reference
self-tests establish executable evaluation coverage, not measured token or wall-time savings
for models. Do not quote a CLI result as billed token savings or fewer model rounds.
