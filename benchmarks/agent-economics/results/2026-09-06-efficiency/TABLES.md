# Complete descriptive tables

Each cell contains three attempted runs. Tokens include cache reads and writes. All medians retain failed attempts; `unknown` means at least one terminal metric is missing. Native turns and visible model responses are different counters.

## phase1

| Task | Model | Arm | Oracle | Guarded AST write | Tokens | Native turns | Tool calls | Wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| local-variable | haiku | compact_focused | 3/3 | 3/3 | 27,569 | 5 | 4 | 16.95 |
| local-variable | haiku | compact_full | 3/3 | 3/3 | 33,735 | 6 | 5 | 18.5 |
| local-variable | haiku | contextual_patch | 3/3 | n/a | 20,244 | 4 | 3 | 11.69 |
| local-variable | haiku | full_skill | 2/3 | 2/3 | 46,098 | 7 | 6 | 20.6 |
| local-variable | sonnet | compact_focused | 3/3 | 3/3 | 14,217 | 3 | 2 | 10.63 |
| local-variable | sonnet | compact_full | 3/3 | 3/3 | 14,033 | 3 | 2 | 8.83 |
| local-variable | sonnet | contextual_patch | 3/3 | n/a | 12,988 | 3 | 2 | 8.93 |
| local-variable | sonnet | full_skill | 3/3 | 0/3 | 22,519 | 4 | 3 | 13.09 |
| multi-file-members | haiku | compact_focused | 3/3 | 3/3 | 16,807 | 4 | 3 | 14.14 |
| multi-file-members | haiku | compact_full | 3/3 | 3/3 | 20,794 | 4 | 3 | 13.79 |
| multi-file-members | haiku | contextual_patch | 3/3 | n/a | 26,665 | 7 | 6 | 14.39 |
| multi-file-members | haiku | full_skill | 2/3 | 2/3 | 41,485 | 8 | 7 | 18.1 |
| multi-file-members | sonnet | compact_focused | 3/3 | 3/3 | 14,759 | 3 | 2 | 12.59 |
| multi-file-members | sonnet | compact_full | 3/3 | 3/3 | 14,449 | 3 | 2 | 11.63 |
| multi-file-members | sonnet | contextual_patch | 3/3 | n/a | 23,715 | 7 | 6 | 14.79 |
| multi-file-members | sonnet | full_skill | 3/3 | 2/3 | 67,777 | 11 | 9 | 32.57 |

## phase2

| Task | Model | Arm | Oracle | Guarded AST write | Tokens | Native turns | Tool calls | Wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public-llm-obsolete-helper | haiku | compact_focused | 3/3 | 3/3 | 94,431 | 8 | 7 | 25.31 |
| public-llm-obsolete-helper | haiku | compact_full | 3/3 | 3/3 | 109,327 | 9 | 8 | 29.58 |
| public-llm-obsolete-helper | haiku | contextual_patch | 3/3 | n/a | 64,572 | 7 | 6 | 19.55 |
| public-llm-obsolete-helper | haiku | full_skill | 3/3 | 3/3 | 183,888 | 13 | 12 | 35.02 |
| public-llm-obsolete-helper | sonnet | compact_focused | 3/3 | 3/3 | 27,449 | 3 | 2 | 15.03 |
| public-llm-obsolete-helper | sonnet | compact_full | 3/3 | 3/3 | 26,032 | 3 | 2 | 12.39 |
| public-llm-obsolete-helper | sonnet | contextual_patch | 3/3 | n/a | 42,310 | 5 | 4 | 16.84 |
| public-llm-obsolete-helper | sonnet | full_skill | 3/3 | 0/3 | 35,707 | 4 | 3 | 15.59 |
| public-passkeys-scoped-variable | haiku | compact_focused | 3/3 | 0/3 | 95,961 | 10 | 9 | 31.92 |
| public-passkeys-scoped-variable | haiku | compact_full | 3/3 | 1/3 | 90,433 | 9 | 8 | 34.23 |
| public-passkeys-scoped-variable | haiku | contextual_patch | 3/3 | n/a | 49,742 | 7 | 6 | 18.63 |
| public-passkeys-scoped-variable | haiku | full_skill | 3/3 | 1/3 | 290,655 | 19 | 18 | 75.92 |
| public-passkeys-scoped-variable | sonnet | compact_focused | 3/3 | 2/3 | 102,303 | 12 | 11 | 66.13 |
| public-passkeys-scoped-variable | sonnet | compact_full | 1/3 | 1/3 | unknown | unknown | 15 | 120.26 |
| public-passkeys-scoped-variable | sonnet | contextual_patch | 3/3 | n/a | 25,261 | 4 | 3 | 14.69 |
| public-passkeys-scoped-variable | sonnet | full_skill | 3/3 | 0/3 | 119,707 | 12 | 11 | 55.97 |

## phase3

| Task | Model | Arm | Oracle | Guarded AST write | Tokens | Native turns | Tool calls | Wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public-llm-obsolete-helper-directed | haiku | compact_focused | 3/3 | 2/3 | 63,866 | 8 | 7 | 25.16 |
| public-llm-obsolete-helper-directed | haiku | compact_full | 3/3 | 3/3 | 99,359 | 8 | 7 | 27.36 |
| public-llm-obsolete-helper-directed | sonnet | compact_focused | 3/3 | 3/3 | 16,892 | 3 | 2 | 11.54 |
| public-llm-obsolete-helper-directed | sonnet | compact_full | 3/3 | 3/3 | 26,081 | 3 | 2 | 14.85 |
| public-passkeys-scoped-variable-directed | haiku | compact_focused | 3/3 | 1/3 | 273,604 | 19 | 18 | 79.72 |
| public-passkeys-scoped-variable-directed | haiku | compact_full | 3/3 | 0/3 | 116,088 | 10 | 9 | 50.02 |
| public-passkeys-scoped-variable-directed | sonnet | compact_focused | 3/3 | 2/3 | 53,798 | 8 | 7 | 45.29 |
| public-passkeys-scoped-variable-directed | sonnet | compact_full | 1/3 | 1/3 | unknown | unknown | 23 | 120.31 |
