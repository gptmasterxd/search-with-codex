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

    def test_medical_expectation_accepts_mixed_language_outcome_headings(self) -> None:
        evals = benchmark.load_evals(ROOT / "benchmarks" / "evals.json")
        medical = next(item for item in evals if item["id"] == 2)
        patterns = medical["expectations"][0]["patterns"]
        report = "## 통증\n결과\n## Opioid 사용량\n결과\n## 보행·기능\n결과"
        self.assertTrue(benchmark.pattern_passed(report, patterns))

    def test_jsonl_metrics_use_final_turn_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
                        json.dumps(
                            {
                                "type": "item.started",
                                "item": {"type": "web_search", "query": "x"},
                            }
                        ),
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
            self.assertEqual(metrics["search_discovery_calls"], 1)
            self.assertEqual(metrics["search_discovery_items"], {"web_search": 1})
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

    def test_judge_uses_one_consistent_five_point_scale(self) -> None:
        schema = json.loads(
            (ROOT / "benchmarks" / "judge_schema.json").read_text(encoding="utf-8")
        )
        score = schema["$defs"]["outputScore"]["properties"]
        self.assertEqual(score["overall"]["minimum"], 1)
        self.assertEqual(score["overall"]["maximum"], 5)
        for name in (
            "correctness",
            "completeness",
            "evidence_quality",
            "uncertainty_handling",
            "decision_usefulness",
        ):
            self.assertEqual(score[name]["minimum"], 1)
            self.assertEqual(score[name]["maximum"], 5)

    def test_judge_score_contract_rejects_inconsistent_overall(self) -> None:
        dimensions = {
            "correctness": 2,
            "completeness": 2,
            "evidence_quality": 2,
            "uncertainty_handling": 2,
            "decision_usefulness": 2,
        }
        valid = {
            "scores": {
                "A": {**dimensions, "overall": 2.5},
                "B": {**dimensions, "overall": 2},
            }
        }
        invalid = {
            "scores": {
                "A": {**dimensions, "overall": 5},
                "B": {**dimensions, "overall": 2},
            }
        }
        self.assertTrue(benchmark.judge_score_contract_valid(valid))
        self.assertFalse(benchmark.judge_score_contract_valid(invalid))

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

    def test_usage_limit_is_an_infrastructure_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            message = (
                "You've hit your usage limit. Visit Codex settings to purchase "
                "more credits or try again tomorrow."
            )
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "error", "message": message}),
                        json.dumps(
                            {
                                "type": "turn.failed",
                                "error": {"message": message},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            metrics = benchmark.parse_jsonl_metrics(path)
            self.assertEqual(metrics["errors"], [message])
            self.assertEqual(
                benchmark.execution_failure_kind(
                    returncode=1,
                    timed_out=False,
                    transcript_metrics=metrics,
                ),
                "usage_limit",
            )

    def test_resume_metadata_allows_commit_change_when_skill_is_identical(self) -> None:
        existing = {
            "repo_root": "/repo",
            "repo_commit": "old",
            "candidate_skill_tree_sha256": "legacy-cache-sensitive-digest",
            "candidate_skill_git_tree": "same-tree",
            "model": "model",
            "codex": "codex",
            "codex_version": "codex 1",
            "evals_path": "/repo/evals.json",
            "eval_ids": [1],
            "configurations": ["with_skill", "without_skill"],
            "baseline_isolation": {"disabled_plugins": []},
        }
        current = {
            **existing,
            "repo_commit": "new",
            "candidate_skill_tree_sha256": "stable-digest",
        }
        benchmark.validate_resume_metadata(existing, current)
        changed = {**current, "candidate_skill_git_tree": "changed-tree"}
        with self.assertRaises(benchmark.BenchmarkError):
            benchmark.validate_resume_metadata(existing, changed)

    def test_candidate_digest_ignores_python_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "script.py").write_text("print('same')\n", encoding="utf-8")
            first = benchmark.tree_digest(root)
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "script.cpython-314.pyc").write_bytes(b"runtime cache")
            self.assertEqual(benchmark.tree_digest(root), first)

    def test_archived_retry_preserves_the_failed_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run"
            run_dir.mkdir()
            (run_dir / "execution.json").write_text("{}", encoding="utf-8")
            (run_dir / "project").mkdir()
            archive = benchmark.archive_run_attempt(run_dir)
            self.assertIsNotNone(archive)
            self.assertTrue((archive / "execution.json").is_file())
            self.assertTrue((archive / "project").is_dir())
            self.assertEqual([path.name for path in run_dir.iterdir()], ["attempts"])

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

    def test_mcp_search_discovery_call_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "mcp_tool_call",
                            "name": "search_query",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            metrics = benchmark.parse_jsonl_metrics(path)
            self.assertEqual(metrics["search_discovery_calls"], 1)
            self.assertEqual(metrics["search_discovery_items"], {"search_query": 1})

    def test_judge_run_contract_enforces_search_budget_and_errors(self) -> None:
        dimensions = {
            "correctness": 4,
            "completeness": 4,
            "evidence_quality": 4,
            "uncertainty_handling": 4,
            "decision_usefulness": 4,
            "overall": 4,
        }
        result = {
            "returncode": 0,
            "timed_out": False,
            "winner": "A",
            "score_contract_valid": True,
            "comparison": {"scores": {"A": dimensions, "B": dimensions}},
            "transcript_metrics": {
                "errors": [],
                "search_discovery_calls": benchmark.JUDGE_MAX_SEARCH_CALLS,
            },
            "search_budget_passed": True,
        }
        self.assertTrue(benchmark.judge_run_contract_valid(result))
        over_budget = {
            **result,
            "transcript_metrics": {
                "errors": [],
                "search_discovery_calls": benchmark.JUDGE_MAX_SEARCH_CALLS + 1,
            },
            "search_budget_passed": False,
        }
        self.assertFalse(benchmark.judge_run_contract_valid(over_budget))
        transcript_error = {
            **result,
            "transcript_metrics": {
                "errors": ["judge search failed"],
                "search_discovery_calls": 1,
            },
        }
        self.assertFalse(benchmark.judge_run_contract_valid(transcript_error))

    def test_successful_execution_requires_report_and_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            benchmark.write_json(
                run_dir / "execution.json",
                {"returncode": 0, "timed_out": False},
            )
            (run_dir / "transcript.jsonl").write_text(
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertFalse(benchmark.successful_execution(run_dir))

            outputs = run_dir / "outputs"
            outputs.mkdir()
            (outputs / "final.md").write_text("usable report", encoding="utf-8")
            self.assertFalse(benchmark.successful_execution(run_dir))

            benchmark.write_json(
                run_dir / "grading.json",
                {"summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0}},
            )
            self.assertTrue(benchmark.successful_execution(run_dir))

    def test_stable_execution_order_is_deterministic_and_balanced(self) -> None:
        evals = benchmark.load_evals(ROOT / "benchmarks" / "evals.json")
        first = benchmark.stable_execution_order(evals, "candidate-tree")
        second = benchmark.stable_execution_order(evals, "candidate-tree")
        self.assertEqual(first, second)
        for eval_case in evals:
            configurations = [
                configuration
                for candidate, configuration in first
                if candidate["id"] == eval_case["id"]
            ]
            self.assertEqual(set(configurations), set(benchmark.CONFIGURATIONS))
            self.assertEqual(len(configurations), len(benchmark.CONFIGURATIONS))

    def test_worker_defaults_serialize_shared_account_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            args = benchmark.build_parser().parse_args(
                ["run", "--workspace", temp]
            )
            self.assertEqual(args.max_workers, 1)
            self.assertEqual(args.judge_workers, 1)


if __name__ == "__main__":
    unittest.main()
