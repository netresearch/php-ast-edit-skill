#!/bin/sh
# shellcheck disable=SC2016 # the patterns name PHP variables; `$` is meant literally
# All three changes, the rename complete at both ends, and the new method actually used.
#
# Its predecessor asked for a private method and for the project's analysis to pass,
# which this configuration cannot both grant: an uncalled private method is a
# method.unused error, so the perfect answer still failed the check. The call site in
# resetLockout() makes the task satisfiable.
f=Classes/Service/RateLimiterService.php
[ -f "$f" ] || exit 1
grep -q 'private function lockoutKeyFor(string \$username, string \$ip): string' "$f" || exit 1
grep -q 'buildLockoutKey' "$f" && exit 1
[ "$(grep -c 'this->lockoutKeyFor(' "$f")" = "4" ] || exit 1
grep -q 'private function clearAttempts(string \$key): void' "$f" || exit 1
grep -q 'this->clearAttempts(' "$f" || exit 1
grep -q 'Refuse the request when the caller has exceeded its budget\.' "$f" || exit 1
grep -q 'private function buildUserLockoutKey(string \$username): string' "$f" || exit 1
# The same bar as task D: the project's own unit tests pass on the tree the run left.
php .Build/bin/phpunit -c Build/phpunit.xml --testsuite unit --no-progress >/dev/null 2>&1 || exit 1
exit 0
