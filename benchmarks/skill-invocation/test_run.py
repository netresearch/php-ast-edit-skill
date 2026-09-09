#!/usr/bin/env python3
"""What run.sh does with the subject's dependencies.

An arm is a full Claude Code session with a real repository in front of it, so it may
run composer. While the arms shared one `.Build` by symlink, one of them did — and
rewrote the subject's autoloader to point its root package at that arm's working
directory, which the next run deleted. The subject's own PHPStan then reported 66
errors against code that parses, every `apply` in every later arm came back
checksPassed:false, and the measurement was answering about itself.

These cases pin the two halves of the fix: an arm gets its own copy of what composer
rewrites, and a subject that is already poisoned stops the run instead of being
measured.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUN = Path(__file__).resolve().parent / "run.sh"
BASE_COMMIT = "the one commit"


def subject(root: Path, install_path: str) -> Path:
    """A git repository whose autoloader names `install_path` (a PHP expression) as root."""
    repo = root / "subject"
    (repo / ".Build" / "vendor" / "composer").mkdir(parents=True)
    (repo / ".Build" / "vendor" / "somepackage").mkdir()
    (repo / ".Build" / "vendor" / "somepackage" / "src.php").write_text("<?php\n")
    (repo / ".Build" / "vendor" / "composer" / "installed.php").write_text(
        "<?php return ['root' => ['install_path' => %s]];\n" % install_path
    )
    (repo / "a.php").write_text("<?php\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    for argv in (["init", "-q", "-b", "main"], ["add", "a.php"],
                 ["commit", "-q", "--no-gpg-sign", "-m", BASE_COMMIT]):
        subprocess.run(["git", *argv], cwd=repo, env=env, check=True)
    return repo


def run(bench: Path, repo: Path, *args: str) -> subprocess.CompletedProcess:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()
    return subprocess.run(
        [str(RUN), *args],
        capture_output=True, text=True,
        env={**os.environ, "BENCH": str(bench), "REPO": str(repo), "BASE": head},
    )


def main() -> int:
    failures = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bench = root / "bench"
        bench.mkdir()

        # A subject whose autoloader points somewhere else entirely — the state a
        # previous arm's `composer dump-autoload` left behind. The run must stop.
        poisoned = subject(root, repr(str(root / "gone" / "work" / "B1-free")))
        result = run(bench, poisoned, "T1", "free", "do nothing")
        check("a poisoned subject stops the run", result.returncode == 2)
        check("it names the root package it found", "B1-free" in result.stderr)
        check("it says how to repair it", "composer install" in result.stderr)
        check("it does not reach the configuration check",
              "no configuration" not in result.stderr)
        shutil.rmtree(poisoned)

        # A healthy subject gets past the guard. There is no cfg-free here, so the
        # run stops at the configuration check — a different message, which is how
        # this case tells "the guard let it through" from "the guard fired".
        healthy = subject(root, "__DIR__ . '/../../../'")
        result = run(bench, healthy, "T2", "free", "do nothing")
        check("a healthy subject passes the guard", "no configuration" in result.stderr)

        work = bench / "work" / "T2-free"
        vendor = work / ".Build" / "vendor"
        check("the arm has its own vendor directory", vendor.is_dir())
        check("it is not a symlink to the subject's", not vendor.is_symlink())

        # The packages are hardlinked: same inode, no second copy on disk.
        package = vendor / "somepackage" / "src.php"
        check("packages are shared by hardlink",
              package.exists()
              and package.stat().st_ino
              == (healthy / ".Build/vendor/somepackage/src.php").stat().st_ino)

        # vendor/composer is what composer rewrites, so it is a real copy. Writing
        # the arm's copy must leave the subject's untouched.
        arm_installed = vendor / "composer" / "installed.php"
        subject_installed = healthy / ".Build" / "vendor" / "composer" / "installed.php"
        check("vendor/composer is copied, not linked",
              arm_installed.stat().st_ino != subject_installed.stat().st_ino)
        before = subject_installed.read_text()
        arm_installed.write_text("<?php return ['root' => ['install_path' => '/gone']];\n")
        check("an arm rewriting its autoloader leaves the subject alone",
              subject_installed.read_text() == before)

    if failures:
        print("FAIL: %d case(s)" % len(failures), file=sys.stderr)
        for name in failures:
            print("  - " + name, file=sys.stderr)
        return 1
    print("OK: run.sh isolates the subject's dependencies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
