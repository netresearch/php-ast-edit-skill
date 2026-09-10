#!/bin/sh
# A public method renamed across the project: declaration and every call, nothing else.
#
# ExtensionConfigurationService::getConfiguration() has 29 calls in 12 files, among them
# the unit test. A text search for the name also finds a comment in that test, which the
# task does not ask about, so the oracle counts code shapes rather than the bare name.
f=Classes/Service/ExtensionConfigurationService.php
[ -f "$f" ] || exit 1
grep -q 'public function configuration(' "$f" || exit 1
grep -rq -e '->getConfiguration(' -e 'function getConfiguration(' Classes Tests && exit 1
[ "$(grep -ro -e '->configuration(' Classes Tests | wc -l)" = "29" ] || exit 1
# Only the twelve files that carry the method may change.
allowed='Classes/Authentication/PasskeyAuthenticationService.php
Classes/Controller/AdminModuleController.php
Classes/Controller/LoginController.php
Classes/Controller/ManagementController.php
Classes/EventListener/InjectPasskeyLoginFields.php
Classes/Service/AssertionService.php
Classes/Service/AttestationService.php
Classes/Service/ChallengeService.php
Classes/Service/ExtensionConfigurationService.php
Classes/Service/RateLimiterService.php
Classes/Service/WebAuthnCeremonyFactory.php
Tests/Unit/Service/ExtensionConfigurationServiceTest.php'
for changed in $(git diff --name-only HEAD); do
  printf '%s\n' "$allowed" | grep -qx "$changed" || exit 1
done
[ -z "$(git ls-files --others --exclude-standard)" ] || exit 1
exit 0
