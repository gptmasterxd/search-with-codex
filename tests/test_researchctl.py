from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CTL = ROOT / "skills" / "insane-research" / "scripts" / "researchctl.py"

spec = importlib.util.spec_from_file_location("researchctl_test", CTL)
assert spec is not None and spec.loader is not None
researchctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(researchctl)


SRC_A = {
    "url": "https://a.example.com/report/?utm_source=test",
    "title": "Primary report",
    "domain": "a.example.com",
    "source_family": "a.example.com",
    "quality_rating": "A",
    "primary": True,
    "published_at": "2026-07-01",
    "valid_at": "2026-07-01",
}
SRC_B = {
    "url": "https://b.example.org/analysis",
    "title": "Independent analysis",
    "domain": "b.example.org",
    "source_family": "b.example.org",
    "quality_rating": "B",
    "primary": False,
    "published_at": "2026-07-02",
    "valid_at": "2026-07-02",
}
SRC_C = {
    "url": "https://c.example.net/data",
    "title": "Independent dataset",
    "domain": "c.example.net",
    "source_family": "c.example.net",
    "quality_rating": "B",
    "primary": False,
    "published_at": "2026-07-03",
    "valid_at": "2026-07-03",
}


def run_ctl(*args: str) -> SimpleNamespace:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        returncode = researchctl.main(list(args))
    return SimpleNamespace(returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ResearchCtlTests(unittest.TestCase):
    def make_session(self, base: Path, mode: str = "standard") -> Path:
        session = base / "session"
        for directory in ("artifacts", "sources", "outputs", "raw"):
            (session / directory).mkdir(parents=True, exist_ok=True)
        write_json(
            session / "state.json",
            {
                "session_id": "session",
                "topic": "fixture",
                "mode": mode,
                "phase": 1,
                "status": "active",
                "verification": {"passed": False},
            },
        )
        return session

    def make_agent_return(self, *, counter_search: str = "No credible refutation found") -> list[dict]:
        return [
            {
                "axis": "official",
                "sources": [copy.deepcopy(SRC_A), copy.deepcopy(SRC_B)],
                "claims": [
                    {
                        "text": "The defined metric was 42 in July 2026.",
                        "risk": "high",
                        "claim_type": "numeric",
                        "source_urls": [
                            "https://a.example.com/report",
                            "https://b.example.org/analysis",
                        ],
                        "counter_search": counter_search,
                        "counter_refuted": False,
                        "conflicting": False,
                        "primary_source": True,
                        "valid_at": "2026-07-01",
                    }
                ],
                "queries_run": ["Metric July 2026", "metric correction July 2026"],
                "search_count": 2,
                "expand_leads": [{"lead": "Check definitions", "why": "May alter denominator", "angle": "metric methodology"}],
                "dead_ends": [],
            },
            {
                "axis": "cross-check",
                "sources": [
                    {
                        **SRC_A,
                        "url": "https://a.example.com/report/",
                        "quality_rating": "B",
                        "title": "Longer primary report title",
                    }
                ],
                "claims": [],
                "queries_run": ["  METRIC   JULY 2026  "],
                "search_count": 1,
                "expand_leads": [],
                "dead_ends": ["No separate historical series"],
            },
        ]

    def test_url_normalization_removes_tracking_and_trailing_slash(self):
        self.assertEqual(
            researchctl.normalize_url("HTTPS://Example.COM:443/a/?utm_source=x&b=2&a=1#frag"),
            "https://example.com/a?a=1&b=2",
        )
        self.assertTrue(researchctl.domains_equivalent("example.com", "www.example.com"))
        self.assertFalse(researchctl.domains_equivalent("example.com", "www.example.net"))
        self.assertEqual(researchctl.normalize_url("https://example.com:not-a-port/x"), "")
        self.assertEqual(researchctl.normalize_url("https://[broken/x"), "")
        self.assertEqual(researchctl.normalize_url("not a valid host/path"), "")
        self.assertEqual(researchctl.normalize_url("file:///etc/passwd"), "")
        self.assertEqual(researchctl.normalize_url("ftp://example.com/archive"), "")
        self.assertEqual(researchctl.normalize_url("https://user:secret@example.com/report"), "")
        self.assertEqual(
            researchctl.normalize_url("https://[2001:db8::1]:8443/a/"),
            "https://[2001:db8::1]:8443/a",
        )
        self.assertEqual(
            researchctl.report_urls(
                "See [source](https://example.com/report/?utm_source=test)."
            ),
            {"https://example.com/report"},
        )

    def test_init_creates_resumable_session(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_ctl(
                "init",
                "--topic",
                "테스트 연구",
                "--root",
                temp,
                "--mode",
                "strict",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            session = Path(payload["session"])
            self.assertTrue((session / "state.json").exists())
            self.assertTrue((session / "artifacts" / "research_plan.md").exists())
            self.assertTrue((session / "artifacts" / "agent_returns").is_dir())
            workspace_session = Path(payload["workspace_session"])
            self.assertEqual(workspace_session.resolve(), session)
            self.assertTrue(str(workspace_session).startswith(str(Path(temp))))
            state = read_json(session / "state.json")
            self.assertEqual(state["mode"], "strict")
            self.assertEqual(state["schema_version"], 3)

    def test_merge_prefers_isolated_per_agent_files_over_legacy_aggregate(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()
            write_json(
                session / "artifacts" / "agent_returns.json",
                {"returns": "invalid legacy value that must be ignored"},
            )
            write_json(session / "artifacts" / "agent_returns" / "01-official.json", returns[0])
            write_json(
                session / "artifacts" / "agent_returns" / "02-cross-check.json",
                {"returns": [returns[1]]},
            )

            result = run_ctl("merge", "--session", str(session), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["input_mode"], "per-agent-directory")
            self.assertEqual(
                payload["input_files"],
                [
                    "artifacts/agent_returns/01-official.json",
                    "artifacts/agent_returns/02-cross-check.json",
                ],
            )
            self.assertEqual(payload["agent_returns"], 2)
            self.assertEqual(len(read_jsonl(session / "sources" / "sources.jsonl")), 2)

    def test_merge_reports_invalid_per_agent_file_path(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            bad_path = session / "artifacts" / "agent_returns" / "01-bad.json"
            write_json(bad_path, {"returns": "not-an-array"})
            result = run_ctl("merge", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn(str(bad_path), result.stderr)

    def test_merge_deduplicates_identical_url_conservatively_and_logs_queries(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            result = run_ctl("merge", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            sources = read_jsonl(session / "sources" / "sources.jsonl")
            self.assertEqual(len(sources), 2)
            a_source = next(source for source in sources if source["domain"] == "a.example.com")
            self.assertEqual(a_source["quality_rating"], "B")  # tie A/B -> conservative B
            self.assertEqual(a_source["url"], "https://a.example.com/report")
            claims = read_jsonl(session / "artifacts" / "claim_ledger.jsonl")
            self.assertEqual(claims[0]["source_ids"], ["src_001", "src_002"])
            query_log = (session / "artifacts" / "query_log.md").read_text(encoding="utf-8")
            self.assertIn("DUP of", query_log)
            self.assertIn("Agent-reported search-tool calls: 3", query_log)
            self.assertIn("Logged query strings: 3", query_log)
            self.assertIn("Unique logged query strings: 2", query_log)
            self.assertIn("Check definitions", (session / "artifacts" / "expansion_log.md").read_text(encoding="utf-8"))

    def test_merge_canonicalizes_observed_agent_aliases_without_parent_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            legacy_source = {
                "url": SRC_A["url"],
                "title": SRC_A["title"],
                "source_family": SRC_A["source_family"],
                "quality": "A",
                "primary": True,
                "published_at": SRC_A["published_at"],
                "accessed_at": "2026-08-06T16:34:12Z",
                "key_points": ["Primary result", "Important limitation"],
                "access_method": "publisher HTML",
                "access_status": "partial",
            }
            legacy_claim = {
                "claim": "Routine intervention does not improve the defined outcome.",
                "risk": "high",
                "causal": True,
                "source_urls": [SRC_A["url"]],
                "counter_source_urls": [],
                "counter_search": "Searched for a credible benefit and found none",
                "counter_refuted": False,
                "conflicting": False,
                "primary_source": True,
                "valid_at": "2026-07-01",
            }
            returns = [
                {
                    "axis": "legacy-agent",
                    "sources": [legacy_source],
                    "claims": [legacy_claim],
                    "queries_run": ["legacy alias check"],
                    "search_count": 1,
                    "expand_leads": ["Check a newly registered trial"],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            result = run_ctl("merge", "--session", str(session), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["warnings"], [])
            self.assertTrue(any("quality→quality_rating" in item for item in payload["normalizations"]))
            self.assertTrue(any("claim→text" in item for item in payload["normalizations"]))
            self.assertTrue(any("string canonicalized" in item for item in payload["normalizations"]))

            source = read_jsonl(session / "sources" / "sources.jsonl")[0]
            self.assertEqual(source["quality_rating"], "A")
            self.assertEqual(source["observed_at"], "2026-08-06T16:34:12Z")
            self.assertEqual(source["notes"], "Primary result; Important limitation")
            self.assertEqual(
                source["access"],
                {"method": "publisher HTML", "status": "partial"},
            )
            claim = read_jsonl(session / "artifacts" / "claim_ledger.jsonl")[0]
            self.assertEqual(claim["text"], legacy_claim["claim"])
            self.assertEqual(claim["claim_type"], "causal")
            expansion_log = (session / "artifacts" / "expansion_log.md").read_text(encoding="utf-8")
            self.assertIn("Check a newly registered trial", expansion_log)

    def test_merge_corrects_declared_domain_from_url(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()[:1]
            returns[0]["sources"][0]["domain"] = "spoofed.example"
            write_json(session / "artifacts" / "agent_returns.json", returns)
            result = run_ctl("merge", "--session", str(session), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(any("URL host" in warning for warning in payload["warnings"]))
            sources = read_jsonl(session / "sources" / "sources.jsonl")
            self.assertEqual(sources[0]["domain"], "a.example.com")

    def test_www_declared_domain_alias_matches_url_host(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()[:1]
            www_url = "https://www.a.example.com/report"
            returns[0]["sources"][0]["url"] = www_url
            returns[0]["sources"][0]["domain"] = "a.example.com"
            returns[0]["claims"][0]["source_urls"][0] = www_url
            write_json(session / "artifacts" / "agent_returns.json", returns)
            result = run_ctl("merge", "--session", str(session), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(any("URL host" in warning for warning in payload["warnings"]))
            sources = read_jsonl(session / "sources" / "sources.jsonl")
            self.assertEqual(sources[0]["domain"], "www.a.example.com")
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)

    def test_distinct_sources_on_one_domain_preserve_grade_and_family(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "family-check",
                    "sources": [
                        {**SRC_A, "source_family": "family-one"},
                        {
                            **SRC_A,
                            "url": "https://a.example.com/second",
                            "title": "Second page",
                            "source_family": "family-two",
                            "quality_rating": "C",
                        },
                    ],
                    "claims": [
                        {
                            "text": "Two pages on one domain do not establish independence.",
                            "risk": "normal",
                            "claim_type": "descriptive",
                            "source_urls": [SRC_A["url"], "https://a.example.com/second"],
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            result = run_ctl("merge", "--session", str(session), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(any("source_family 충돌" in warning for warning in payload["warnings"]))
            sources = read_jsonl(session / "sources" / "sources.jsonl")
            self.assertEqual(
                {(source["source_family"], source["quality_rating"]) for source in sources},
                {("family-one", "A"), ("family-two", "C")},
            )
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            verified = read_json(session / "outputs" / "verified_claims.json")
            self.assertEqual(len(verified), 1)

    def test_conflicting_families_for_identical_url_collapse_to_domain(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()
            returns[0]["sources"][0]["source_family"] = "family-one"
            returns[1]["sources"][0]["source_family"] = "family-two"
            write_json(session / "artifacts" / "agent_returns.json", returns)
            result = run_ctl("merge", "--session", str(session), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(any("동일 URL source_family 충돌" in warning for warning in payload["warnings"]))
            sources = read_jsonl(session / "sources" / "sources.jsonl")
            a_source = next(source for source in sources if source["domain"] == "a.example.com")
            self.assertEqual(a_source["source_family"], "a.example.com")

    def test_shared_family_across_domains_is_not_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()[:1]
            returns[0]["sources"][0]["source_family"] = "shared-wire"
            returns[0]["sources"][1]["source_family"] = "shared-wire"
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            unresolved = read_json(session / "outputs" / "unresolved_claims.json")
            self.assertEqual(len(unresolved), 1)
            self.assertIn("독립 출처 계열 1개", unresolved[0]["status_reason"])

    def test_duplicate_claims_merge_evidence_across_agents(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            claim_text = "The merged metric was 42 in July 2026."
            returns = [
                {
                    "axis": "primary",
                    "sources": [copy.deepcopy(SRC_A)],
                    "claims": [
                        {
                            "text": claim_text,
                            "risk": "high",
                            "claim_type": "numeric",
                            "source_urls": [SRC_A["url"]],
                            "counter_search": "Checked official corrections; none found.",
                            "primary_source": True,
                            "valid_at": "2026-07-01",
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                },
                {
                    "axis": "independent",
                    "sources": [copy.deepcopy(SRC_B)],
                    "claims": [
                        {
                            "text": claim_text,
                            "risk": "high",
                            "claim_type": "numeric",
                            "source_urls": [SRC_B["url"]],
                            "counter_search": "Checked independent criticism; none defeated the claim.",
                            "primary_source": False,
                            "valid_at": "2026-07-01",
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                },
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            claims = read_jsonl(session / "artifacts" / "claim_ledger.jsonl")
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0]["source_ids"], ["src_001", "src_002"])
            self.assertEqual(claims[0]["axes"], ["primary", "independent"])
            self.assertIn("official corrections", claims[0]["counter_search"])
            self.assertIn("independent criticism", claims[0]["counter_search"])
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            self.assertEqual(len(read_json(session / "outputs" / "verified_claims.json")), 1)

    def test_standard_validation_verifies_high_risk_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            verified = read_json(session / "outputs" / "verified_claims.json")
            self.assertEqual(len(verified), 1)
            state = read_json(session / "state.json")
            self.assertTrue(state["verification"]["passed"])
            self.assertEqual(len(state["verification"]["signature"]), 64)

            brief_result = run_ctl("brief", "--session", str(session))
            self.assertEqual(brief_result.returncode, 0, brief_result.stderr)
            brief = json.loads(brief_result.stdout)
            self.assertEqual(len(brief["sources"]), 2)
            self.assertEqual(len(brief["verified_claims"]), 1)
            self.assertEqual(brief["unresolved_claims"], [])
            self.assertEqual(brief["refuted_claims"], [])
            self.assertEqual(
                brief["verified_claims"][0]["source_ids"],
                ["src_001", "src_002"],
            )
            self.assertEqual(
                brief["verified_claims"][0]["claim_scope"],
                "synthesized",
            )
            self.assertNotIn("notes", brief["sources"][0])

    def test_missing_counter_search_is_exit_one(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return(counter_search=""))
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("counter_search", result.stderr)

    def test_primary_claim_flag_must_be_backed_by_primary_source_record(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "primary-consistency",
                    "sources": [copy.deepcopy(SRC_B), copy.deepcopy(SRC_C)],
                    "claims": [
                        {
                            "text": "A high-risk claim with an unbacked primary flag.",
                            "risk": "high",
                            "claim_type": "numeric",
                            "source_urls": [SRC_B["url"], SRC_C["url"]],
                            "counter_search": "No refutation found.",
                            "primary_source": True,
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            unresolved = read_json(session / "outputs" / "unresolved_claims.json")
            self.assertEqual(len(unresolved), 1)
            self.assertIn("source registry", unresolved[0]["status_reason"])

    def test_counter_refuted_without_evidence_is_process_violation(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "counter",
                    "sources": [],
                    "claims": [
                        {
                            "text": "An unsupported refutation marker must not pass.",
                            "risk": "high",
                            "claim_type": "causal",
                            "source_urls": [],
                            "counter_search": "A counter search was claimed.",
                            "counter_refuted": True,
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            self.assertIn("반증 출처", result.stderr)

    def test_counter_refuted_cannot_reuse_supporting_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "counter",
                    "sources": [copy.deepcopy(SRC_B)],
                    "claims": [
                        {
                            "text": "A claim defeated by registered counter-evidence.",
                            "risk": "high",
                            "claim_type": "causal",
                            "source_urls": [SRC_B["url"]],
                            "counter_search": "Independent evidence directly contradicted the claim.",
                            "counter_refuted": True,
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            self.assertIn("별도로 등록된 반증 출처", result.stderr)

    def test_counter_refuted_with_explicit_counter_evidence_is_refuted(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "counter",
                    "sources": [copy.deepcopy(SRC_A), copy.deepcopy(SRC_B)],
                    "claims": [
                        {
                            "text": "A claim defeated by separately registered counter-evidence.",
                            "risk": "high",
                            "claim_type": "causal",
                            "source_urls": [SRC_A["url"]],
                            "counter_source_urls": [SRC_B["url"]],
                            "counter_search": "Independent evidence directly contradicted the claim.",
                            "counter_refuted": True,
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            claim = read_jsonl(session / "artifacts" / "claim_ledger.jsonl")[0]
            self.assertEqual(claim["source_ids"], ["src_001"])
            self.assertEqual(claim["counter_source_ids"], ["src_002"])
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            self.assertEqual(len(read_json(session / "outputs" / "refuted_claims.json")), 1)

    def test_counter_refuted_rejects_overlapping_support_and_counter_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "counter-overlap",
                    "sources": [copy.deepcopy(SRC_A)],
                    "claims": [
                        {
                            "text": "The same source cannot be both support and sole refutation.",
                            "risk": "high",
                            "claim_type": "causal",
                            "source_urls": [SRC_A["url"]],
                            "counter_source_urls": [SRC_A["url"]],
                            "counter_search": "A correction route was checked.",
                            "counter_refuted": True,
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            self.assertIn("분리되지 않음", result.stderr)

    def test_unknown_counter_source_id_is_hard_error_exit_two(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            (session / "sources" / "sources.jsonl").write_text(
                json.dumps({"id": "src_001", **SRC_A}) + "\n", encoding="utf-8"
            )
            (session / "artifacts" / "claim_ledger.jsonl").write_text(
                json.dumps(
                    {
                        "claim_id": "clm_001",
                        "text": "Unknown counter source claim",
                        "risk": "high",
                        "claim_type": "causal",
                        "source_ids": ["src_001"],
                        "counter_source_ids": ["src_999"],
                        "counter_search": "Counter route checked.",
                        "counter_refuted": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("counter source id", result.stderr)

    def test_unknown_source_id_is_hard_error_exit_two(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            (session / "sources" / "sources.jsonl").write_text(
                json.dumps({"id": "src_001", **SRC_A}) + "\n", encoding="utf-8"
            )
            (session / "artifacts" / "claim_ledger.jsonl").write_text(
                json.dumps(
                    {
                        "claim_id": "clm_001",
                        "text": "Unknown source claim",
                        "risk": "normal",
                        "claim_type": "descriptive",
                        "source_ids": ["src_999"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("src_999", result.stderr)

    def test_strict_mode_verifies_with_two_strong_source_families(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), mode="strict")
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(read_json(session / "outputs" / "verified_claims.json")), 1)

    def test_attributed_high_risk_claim_accepts_one_directly_inspected_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), mode="strict")
            source = copy.deepcopy(SRC_A)
            source["access"] = {"method": "browser", "status": "ok"}
            returns = self.make_agent_return()
            returns[0]["sources"] = [source]
            returns[0]["claims"][0].update(
                {
                    "text": "Article 53 directly requires the stated disclosure.",
                    "claim_type": "legal",
                    "claim_scope": "attributed",
                    "attribution": "Article 53",
                    "source_urls": [SRC_A["url"]],
                }
            )
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            verified = read_json(session / "outputs" / "verified_claims.json")
            self.assertEqual(len(verified), 1)
            self.assertEqual(verified[0]["claim_scope"], "attributed")
            self.assertIn("직접 귀속", verified[0]["status_reason"])
            brief = json.loads(run_ctl("brief", "--session", str(session)).stdout)
            self.assertEqual(brief["verified_claims"][0]["claim_scope"], "attributed")
            self.assertEqual(brief["verified_claims"][0]["attribution"], "Article 53")

    def test_attributed_claim_requires_direct_source_access(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), mode="strict")
            source = copy.deepcopy(SRC_A)
            source["access"] = {"method": "web-search", "status": "partial"}
            returns = self.make_agent_return()
            returns[0]["sources"] = [source]
            returns[0]["claims"][0].update(
                {
                    "text": "The named trial reported the stated endpoint.",
                    "claim_scope": "attributed",
                    "attribution": "named trial",
                    "source_urls": [SRC_A["url"]],
                }
            )
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            unresolved = read_json(session / "outputs" / "unresolved_claims.json")
            self.assertEqual(len(unresolved), 1)
            self.assertIn("직접 열람한", unresolved[0]["status_reason"])

    def test_attributed_review_result_survives_conflicting_study(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), mode="strict")
            source = copy.deepcopy(SRC_A)
            source["primary"] = False
            source["access"] = {"method": "browser", "status": "ok"}
            returns = self.make_agent_return()
            returns[0]["sources"] = [source]
            returns[0]["claims"][0].update(
                {
                    "text": "The named meta-analysis reported no pooled opioid reduction.",
                    "claim_scope": "attributed",
                    "attribution": "named meta-analysis",
                    "source_urls": [SRC_A["url"]],
                    "conflicting": True,
                    "counter_search": "A different trial reported an early benefit.",
                }
            )
            write_json(session / "artifacts" / "agent_returns.json", returns[:1])
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            verified = read_json(session / "outputs" / "verified_claims.json")
            self.assertEqual(len(verified), 1)
            self.assertIn("상충은 합성", verified[0]["status_reason"])

    def test_causal_claim_cannot_use_attributed_shortcut(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), mode="strict")
            source = copy.deepcopy(SRC_A)
            source["access"] = {"method": "browser", "status": "ok"}
            returns = self.make_agent_return()
            returns[0]["sources"] = [source]
            returns[0]["claims"][0].update(
                {
                    "text": "The named trial proves that the intervention causes recovery.",
                    "claim_type": "causal",
                    "claim_scope": "attributed",
                    "attribution": "named trial",
                    "source_urls": [SRC_A["url"]],
                }
            )
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            unresolved = read_json(session / "outputs" / "unresolved_claims.json")
            self.assertIn("causal", unresolved[0]["status_reason"])

    def test_strict_mode_requires_two_strong_source_families(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), mode="strict")
            returns = self.make_agent_return()
            returns[0]["sources"][1]["quality_rating"] = "D"
            weak_c = {**SRC_C, "quality_rating": "E"}
            returns[0]["sources"].append(weak_c)
            returns[0]["claims"][0]["source_urls"].append(weak_c["url"])
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            unresolved = read_json(session / "outputs" / "unresolved_claims.json")
            self.assertEqual(len(unresolved), 1)
            self.assertIn("A/B 출처 계열 1개 < 2", unresolved[0]["status_reason"])

    def test_executable_claim_requires_and_accepts_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "runtime",
                    "sources": [SRC_A],
                    "claims": [
                        {
                            "text": "The fixture command prints OK.",
                            "risk": "high",
                            "claim_type": "executable",
                            "source_urls": [SRC_A["url"]],
                            "execution_proof": {
                                "script": "python3 fixture.py",
                                "output": "OK",
                                "env": "Python 3.13",
                                "verdict": "confirmed",
                            },
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(read_json(session / "outputs" / "verified_claims.json")), 1)

    def test_executable_claim_requires_environment_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = [
                {
                    "axis": "runtime",
                    "sources": [SRC_A],
                    "claims": [
                        {
                            "text": "The fixture command prints OK without environment metadata.",
                            "risk": "high",
                            "claim_type": "executable",
                            "source_urls": [SRC_A["url"]],
                            "execution_proof": {
                                "script": "python3 fixture.py",
                                "output": "OK",
                                "verdict": "confirmed",
                            },
                        }
                    ],
                    "queries_run": [],
                    "search_count": 0,
                    "expand_leads": [],
                    "dead_ends": [],
                }
            ]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            self.assertIn("script/output/env/verdict", result.stderr)

    def test_hard_error_invalidates_previous_verified_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            self.assertEqual(len(read_json(session / "outputs" / "verified_claims.json")), 1)
            claims = read_jsonl(session / "artifacts" / "claim_ledger.jsonl")
            claims[0]["source_ids"] = ["src_999"]
            (session / "artifacts" / "claim_ledger.jsonl").write_text(
                "\n".join(json.dumps(claim) for claim in claims) + "\n",
                encoding="utf-8",
            )
            result = run_ctl("validate", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(read_json(session / "outputs" / "verified_claims.json"), [])
            state = read_json(session / "state.json")
            self.assertFalse(state["verification"]["passed"])
            self.assertIsNone(state["verification"]["signature"])

    def test_eval_requires_successful_verification_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            (session / "outputs" / "01_full_report.md").write_text("# Report\n", encoding="utf-8")
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("검증 게이트", result.stderr)

    def test_eval_rejects_stale_verification_after_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe defined metric was 42 in July 2026. "
                "[src_001](https://a.example.com/report) "
                "[src_002](https://b.example.org/analysis)\n",
                encoding="utf-8",
            )
            ledger = session / "artifacts" / "claim_ledger.jsonl"
            ledger.write_text(ledger.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("검증 이후", result.stderr)
            state = read_json(session / "state.json")
            self.assertFalse(state["verification"]["passed"])
            self.assertTrue(state["verification"]["stale"])

    def test_eval_signature_covers_unresolved_output(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()[:1]
            returns[0]["claims"][0]["source_urls"] = [SRC_A["url"]]
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            write_json(session / "outputs" / "unresolved_claims.json", [])
            (session / "outputs" / "01_full_report.md").write_text("# Report\n", encoding="utf-8")
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("검증 상태 산출물", result.stderr)

    def test_eval_rejects_tampered_verification_report(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            report_path = session / "outputs" / "verification_report.json"
            report = read_json(report_path)
            report["signature"] = "0" * 64
            write_json(report_path, report)
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("verification_report", result.stderr)

    def test_eval_rejects_tampered_verification_report_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            report_path = session / "outputs" / "verification_report.json"
            report = read_json(report_path)
            report["counts"]["verified"] = 999
            write_json(report_path, report)
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 2)
            self.assertIn("verification_report", result.stderr)

    def test_merge_regresses_phase_and_invalidates_previous_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()
            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe defined metric was 42 in July 2026. "
                "[src_001](https://a.example.com/report) "
                "[src_002](https://b.example.org/analysis)\n",
                encoding="utf-8",
            )
            self.assertEqual(run_ctl("eval", "--session", str(session)).returncode, 0)
            completed = read_json(session / "state.json")
            self.assertEqual(completed["phase"], 7)
            self.assertTrue(completed["evaluation"]["passed"])

            write_json(session / "artifacts" / "agent_returns.json", returns)
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            merged = read_json(session / "state.json")
            self.assertEqual(merged["phase"], 4)
            self.assertFalse(merged["verification"]["passed"])
            self.assertNotIn("evaluation", merged)

            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            revalidated = read_json(session / "state.json")
            self.assertEqual(revalidated["phase"], 6)
            self.assertNotIn("evaluation", revalidated)

    def test_report_eval_passes_with_registered_citations(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe defined metric was 42 in July 2026. "
                "[src_001](https://a.example.com/report/?utm_campaign=test) "
                "[src_002](https://b.example.org/analysis)\n\n"
                "## Unresolved claims\n\nNone.\n\n## Refuted claims\n\nNone.\n",
                encoding="utf-8",
            )
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            report = read_json(session / "outputs" / "eval_report.json")
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["metrics"]["citation_url_coverage_rate"], 1.0)
            self.assertEqual(report["missing_citation_urls"], [])

    def test_report_eval_rejects_source_markers_without_visible_urls(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe defined metric was 42 in July 2026. [src_001] [src_002]\n",
                encoding="utf-8",
            )

            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            report = read_json(session / "outputs" / "eval_report.json")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertEqual(report["metrics"]["citation_url_coverage_rate"], 0.0)
            self.assertEqual(
                [item["source_id"] for item in report["missing_citation_urls"]],
                ["src_001", "src_002"],
            )

    def test_verified_coverage_requires_claim_text_and_adjacent_citation(self):
        claim = {
            "claim_id": "clm_001",
            "text": "The defined metric was 42 in July 2026.",
            "source_ids": ["src_001", "src_002"],
        }
        self.assertFalse(
            researchctl._verified_claim_present(
                claim,
                "A different statement appears here. [src_001] [src_002]",
            )
        )
        self.assertFalse(
            researchctl._verified_claim_present(
                claim,
                "The defined metric was 42 in July 2026.\n\n[src_001] [src_002]",
            )
        )
        self.assertTrue(
            researchctl._verified_claim_present(
                claim,
                "The defined metric was 42 in July 2026. [src_001]",
            )
        )

    def test_attributed_verified_coverage_requires_visible_attribution(self):
        claim = {
            "claim_id": "clm_001",
            "text": "Article 53 directly requires technical documentation and training-content disclosure.",
            "claim_scope": "attributed",
            "attribution": "Article 53",
            "source_ids": ["src_001"],
        }
        self.assertFalse(
            researchctl._verified_claim_present(
                claim,
                "The rule directly requires technical documentation and training-content "
                "disclosure. [src_001](https://example.org/source)",
            )
        )
        self.assertTrue(
            researchctl._attributed_claim_generalized(
                claim,
                "The rule directly requires technical documentation and training-content "
                "disclosure. [src_001](https://example.org/source)",
            )
        )
        self.assertTrue(
            researchctl._verified_claim_present(
                claim,
                "Article 53 directly requires technical documentation and training-content "
                "disclosure. [src_001](https://example.org/source)",
            )
        )
        self.assertFalse(
            researchctl._attributed_claim_generalized(
                claim,
                "Article 53 directly requires technical documentation and training-content "
                "disclosure. [src_001](https://example.org/source)",
            )
        )

    def test_attributed_coverage_accepts_natural_paraphrase_and_canonical_url(self):
        claim = {
            "claim_id": "clm_001",
            "text": (
                "The 2025 Gleicher et al. randomized trial (PMID 40935408) reported "
                "higher recovery scores and lower pain through POD3."
            ),
            "claim_scope": "attributed",
            "attribution": "The 2025 Gleicher et al. randomized trial (PMID 40935408)",
            "source_ids": ["src_001"],
        }
        body = (
            "2025년 Gleicher 무작위시험은 POD3까지 회복 점수가 높고 통증이 "
            "낮았다고 보고했다. "
            "[Gleicher RCT](https://pubmed.ncbi.nlm.nih.gov/40935408/)"
        )
        self.assertTrue(
            researchctl._verified_claim_present(
                claim,
                body,
                {"src_001": "https://pubmed.ncbi.nlm.nih.gov/40935408"},
            )
        )

    def test_report_eval_counts_descriptive_registered_links_as_citations(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            write_json(session / "artifacts" / "agent_returns.json", self.make_agent_return())
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe defined metric was 42 in July 2026. "
                "[Primary report](https://a.example.com/report) "
                "[Independent analysis](https://b.example.org/analysis)\n\n"
                "## Unresolved claims\n\nNone.\n\n## Refuted claims\n\nNone.\n",
                encoding="utf-8",
            )
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)
            report = read_json(session / "outputs" / "eval_report.json")
            self.assertEqual(report["counts"]["cited_sources"], 2)
            self.assertEqual(report["counts"]["cited_sources_with_visible_url"], 2)

    def test_unresolved_leak_matching_does_not_combine_unrelated_paragraphs(self):
        claim = {
            "claim_id": "clm_004",
            "text": (
                "Node 런타임은 tsconfig.json을 읽지 않으므로 paths와 downlevel 변환 등 "
                "tsconfig 의존 기능은 실행 시 적용되지 않는다."
            ),
        }
        body = (
            "`paths` alias가 필요한 저장소는 기존 빌드를 유지한다.\n\n"
            "런타임은 타입 검사를 대신하지 않으므로 CI에서 tsconfig 설정을 유지한다.\n\n"
            "별도 번들러가 downlevel 변환을 담당할 수 있다."
        )
        self.assertFalse(researchctl._claim_text_present_in_body(claim, body))
        self.assertTrue(
            researchctl._claim_text_present_in_body(
                claim,
                "Node 런타임은 tsconfig.json을 읽지 않으므로 paths와 downlevel 변환 등 "
                "tsconfig 의존 기능은 실행 시 적용되지 않는다.",
            )
        )

    def test_report_eval_rejects_unresolved_claim_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()
            returns[0]["claims"][0]["source_urls"] = [SRC_A["url"]]
            write_json(session / "artifacts" / "agent_returns.json", returns[:1])
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe defined metric was 42 in July 2026. [src_001]\n",
                encoding="utf-8",
            )
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 1)
            report = read_json(session / "outputs" / "eval_report.json")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertEqual(report["counts"]["leaked_claims"], 1)

    def test_unresolved_claim_is_allowed_in_annex(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            returns = self.make_agent_return()
            returns[0]["claims"][0]["source_urls"] = [SRC_A["url"]]
            write_json(session / "artifacts" / "agent_returns.json", returns[:1])
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nNo verified conclusion. "
                "[src_001](https://a.example.com/report)\n\n"
                "## Unresolved claims\n\nThe defined metric was 42 in July 2026. "
                "[src_001](https://a.example.com/report)\n",
                encoding="utf-8",
            )
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_shared_source_does_not_create_false_unresolved_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            # One unresolved claim exists, but the main body cites its source for a different sentence.
            returns = self.make_agent_return()
            returns[0]["claims"][0]["source_urls"] = [SRC_A["url"]]
            write_json(session / "artifacts" / "agent_returns.json", returns[:1])
            self.assertEqual(run_ctl("merge", "--session", str(session)).returncode, 0)
            self.assertEqual(run_ctl("validate", "--session", str(session)).returncode, 0)
            (session / "outputs" / "01_full_report.md").write_text(
                "# Report\n\nThe agency published a report in July. "
                "[src_001](https://a.example.com/report)\n",
                encoding="utf-8",
            )
            result = run_ctl("eval", "--session", str(session))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_claim_id_alone_does_not_satisfy_verified_coverage(self):
        claim = {
            "claim_id": "clm_001",
            "text": "The actual material conclusion is forty-two.",
            "claim_scope": "synthesized",
            "source_ids": ["src_001"],
        }
        body = "clm_001 [source](https://example.org/source)"
        self.assertFalse(researchctl._claim_text_present(claim, body))
        self.assertFalse(
            researchctl._verified_claim_present(
                claim,
                body,
                {"src_001": "https://example.org/source"},
            )
        )

    def test_attributed_coverage_requires_material_result_content(self):
        claim = {
            "claim_id": "clm_001",
            "text": (
                "Article 53 directly requires technical documentation and "
                "training-content disclosure."
            ),
            "claim_scope": "attributed",
            "attribution": "Article 53",
            "source_ids": ["src_001"],
        }
        source_map = {"src_001": "https://example.org/article-53"}
        authority_only = (
            "Article 53 is discussed here, but this paragraph only describes "
            "the enforcement authority. "
            "[Article 53](https://example.org/article-53)"
        )
        self.assertFalse(
            researchctl._verified_claim_present(
                claim,
                authority_only,
                source_map,
            )
        )
        matching = (
            "Article 53 requires technical documentation and disclosure of "
            "training-content information. "
            "[Article 53](https://example.org/article-53)"
        )
        self.assertTrue(
            researchctl._verified_claim_present(
                claim,
                matching,
                source_map,
            )
        )

    def test_attributed_generalization_uses_material_content_not_claim_id(self):
        claim = {
            "claim_id": "clm_001",
            "text": "The named trial reported lower pain and better recovery through POD3.",
            "claim_scope": "attributed",
            "attribution": "The named trial",
            "source_ids": ["src_001"],
        }
        source_map = {"src_001": "https://example.org/trial"}
        generalized = (
            "Pain was lower and recovery was better through POD3. "
            "[study](https://example.org/trial)"
        )
        self.assertTrue(
            researchctl._attributed_claim_generalized(
                claim,
                generalized,
                source_map,
            )
        )
        self.assertFalse(
            researchctl._attributed_claim_generalized(
                claim,
                "clm_001 [study](https://example.org/trial)",
                source_map,
            )
        )

    def test_atomic_write_text_uses_unique_temp_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "shared.json"
            payloads = [str(index) * 5000 for index in range(24)]
            with ThreadPoolExecutor(max_workers=12) as executor:
                list(
                    executor.map(
                        lambda payload: researchctl.atomic_write_text(path, payload),
                        payloads,
                    )
                )
            self.assertIn(path.read_text(encoding="utf-8"), payloads)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
