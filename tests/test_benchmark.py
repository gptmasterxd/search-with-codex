from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "benchmarks" / "benchmark.py"
SPEC = importlib.util.spec_from_file_location("benchmark_harness", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class BenchmarkHarnessTests(unittest.TestCase):
    def test_eval_contract_loads_three_unique_cases(self) -> None:
        evals = benchmark.load_evals(ROOT / "benchmarks" / "evals.json")
        self.assertEqual([item["id"] for item in evals], [1, 2, 3])
        self.assertEqual({item["mode"] for item in evals}, {"standard", "strict"})

    def test_jsonl_metrics_use_final_turn_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
                        json.dumps(
                            {
                                "type": "item.completed",
                                "item": {"type": "web_search", "query": "x"},
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn.completed",
                                "usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 20,
                                    "output_tokens": 10,
                                    "reasoning_output_tokens": 5,
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            metrics = benchmark.parse_jsonl_metrics(path)
            self.assertEqual(metrics["thread_id"], "thread-1")
            self.assertEqual(metrics["total_tokens"], 110)
            self.assertEqual(metrics["item_types"], {"web_search": 1})
            self.assertEqual(metrics["tool_item_types"], {"web_search": 1})
            self.assertEqual(metrics["total_tool_calls"], 1)
            self.assertEqual(metrics["warnings"], [])

    def test_blind_mapping_is_stable_and_balanced(self) -> None:
        first = benchmark.stable_blind_mapping("case", "abc")
        second = benchmark.stable_blind_mapping("case", "abc")
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"A", "B"})
        self.assertEqual(set(first.values()), {"with_skill", "without_skill"})

    def test_stats_are_population_statistics(self) -> None:
        result = benchmark.stat([1.0, 2.0, 3.0])
        self.assertEqual(result["mean"], 2.0)
        self.assertAlmostEqual(result["stddev"], 0.816497)

    def test_primary_report_excludes_internal_audit_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            (outputs / "final.md").write_text("handoff", encoding="utf-8")
            (outputs / "research-01_full_report.md").write_text(
                "primary report", encoding="utf-8"
            )
            (outputs / "research-verification_report.json").write_text(
                '{"passed": true}', encoding="utf-8"
            )
            path, text = benchmark.primary_report(outputs)
            self.assertIsNotNone(path)
            self.assertEqual(path.name, "research-01_full_report.md")
            self.assertEqual(text, "primary report")

    def test_external_skill_discovery_excludes_system_skills(self) -> None:
        paths = benchmark.external_skill_paths(())
        self.assertTrue(all(path.name == "SKILL.md" for path in paths))
        self.assertEqual(paths, tuple(sorted(set(paths), key=str)))
        self.assertTrue(all(".system" not in path.parts for path in paths))

    def test_nonfatal_skill_budget_diagnostic_is_not_an_execution_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "error",
                            "message": benchmark.NONFATAL_DIAGNOSTICS[0]
                            + " More detail.",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            metrics = benchmark.parse_jsonl_metrics(path)
            self.assertEqual(metrics["errors"], [])
            self.assertEqual(len(metrics["warnings"]), 1)

    def test_atomic_writes_are_safe_for_concurrent_same_path_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "shared.json"
            payloads = [
                {"writer": index, "payload": str(index) * 10000}
                for index in range(24)
            ]
            with ThreadPoolExecutor(max_workers=12) as executor:
                list(executor.map(lambda value: benchmark.write_json(path, value), payloads))
            self.assertIn(json.loads(path.read_text(encoding="utf-8")), payloads)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
