"""Different documented usage scopes must not hide missing or impossible counters."""

import copy
import unittest

import accounting

MODEL = "claude-haiku-4-5-20251001"


def events():
    return [
        {
            "type": "system",
            "subtype": "init",
            "model": MODEL,
            "tools": ["Bash", "Read", "Edit", "Write"],
            "plugins": [],
            "skills": [],
            "mcp_servers": [],
        },
        {
            "type": "assistant",
            "message": {
                "id": "response-1",
                "model": MODEL,
                "usage": {
                    "input_tokens": 2,
                    "cache_read_input_tokens": 3,
                    "cache_creation_input_tokens": 4,
                },
                "content": [],
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "total_cost_usd": 0.001,
            "usage": {
                "input_tokens": 2,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 4,
                "output_tokens": 5,
            },
            "modelUsage": {
                MODEL: {
                    "inputTokens": 4,
                    "cacheReadInputTokens": 3,
                    "cacheCreationInputTokens": 4,
                    "outputTokens": 6,
                    "costUSD": 0.001,
                }
            },
        },
    ]


class AccountingTests(unittest.TestCase):
    def test_whole_call_and_main_loop_are_kept_separate(self):
        result = accounting.summarize(events(), MODEL)
        self.assertEqual(17, result["all_model_tokens"]["totalTokens"])
        self.assertEqual(14, result["main_loop_tokens"]["totalTokens"])
        self.assertEqual(2, result["whole_call_minus_main_loop"]["inputTokens"])
        self.assertEqual(1, result["primary_model_rounds"])
        self.assertTrue(result["primary_model_rounds_exact"])

    def test_missing_negative_and_inconsistent_counters_still_fail(self):
        for change in (
            "missing",
            "negative",
            "main_exceeds",
            "visible_gap",
            "cost_gap",
        ):
            trace = copy.deepcopy(events())
            model = trace[-1]["modelUsage"][MODEL]
            if change == "missing":
                del model["inputTokens"]
            elif change == "negative":
                model["outputTokens"] = -1
            elif change == "main_exceeds":
                model["inputTokens"] = 1
            elif change == "visible_gap":
                trace[1]["message"]["usage"]["input_tokens"] = 1
            else:
                model["costUSD"] = 0.002
            with self.subTest(change=change), self.assertRaises(ValueError):
                accounting.summarize(trace, MODEL)


if __name__ == "__main__":
    unittest.main()
