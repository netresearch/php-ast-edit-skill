#!/bin/sh
# A public method renamed across the project: declaration and every call, and the project's
# own unit tests still passing.
#
# ExtensionConfigurationService::getConfiguration() has 29 calls in 12 files. Nine more test
# files name it as a string, in PHPUnit mocks (`->method('getConfiguration')`); a rename that
# leaves those fails 174 of the 682 unit tests. The first version of this oracle allowed only
# the twelve files with calls, so it failed the complete answer and passed the broken one
# (PROTOCOL.md, Deviations). The unit suite now decides what "complete" means; the shape
# checks stay, counted as code shapes rather than the bare name, because a comment in the
# test mentions it.
f=Classes/Service/ExtensionConfigurationService.php
[ -f "$f" ] || exit 1
grep -q 'public function configuration(' "$f" || exit 1
grep -rq -e '->getConfiguration(' -e 'function getConfiguration(' Classes Tests && exit 1
[ "$(grep -ro -e '->configuration(' Classes Tests | wc -l)" = "29" ] || exit 1
# Only PHP under Classes/ and Tests/ may change, and nothing may be added.
for changed in $(git diff --name-only HEAD); do
  case "$changed" in
    Classes/*.php | Tests/*.php) ;;
    *) exit 1 ;;
  esac
done
[ -z "$(git ls-files --others --exclude-standard)" ] || exit 1
php .Build/bin/phpunit -c Build/phpunit.xml --testsuite unit --no-progress >/dev/null 2>&1 || exit 1
exit 0
