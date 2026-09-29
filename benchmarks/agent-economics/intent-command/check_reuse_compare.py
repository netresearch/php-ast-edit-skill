#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Compare the paired check-reuse instruction arms."""

from unchanged_compare import CHECK_REUSE_ARMS
from unchanged_compare import main as compare_main


def main(argv=None):
    return compare_main(argv, arms=CHECK_REUSE_ARMS)


if __name__ == "__main__":
    raise SystemExit(main())
