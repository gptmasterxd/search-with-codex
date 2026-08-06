#!/usr/bin/env python3
"""Run and judge real Codex baseline-versus-skill research benchmarks."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVALS = Path(__file__).with_name("evals.json")
JUDGE_SCHEMA = Path(__file__).with_name("judge_schema.json")
CONFIGURATIONS = ("with_skill", "without_skill")
URL_RE = re.compile(r"https?://[^\s<>()\]\[\"']+")
LIMIT_RE = re.compile(
    r"한계|제한|불확실|상충|반대|예외|근거\s*부족|counter|limitation|uncertain",
    re.IGNORECASE,
)
PRIMARY_REPORT_NAMES = (
    "research-01_full_report.md",
    "final.md",
    "research-00_executive_summary.md",
)
TOOL_ITEM_TYPES = {
    "collaboration_tool_call",
    "command_execution",
    "computer_tool_call",
    "dynamic_tool_call",
    "file_change",
    "image_generation",
    "mcp_tool_call",
    "web_search",
}
JUDGE_DIMENSIONS = (
    "correctness",
    "completeness",
    "evidence_quality",
    "uncertainty_handling",
    "decision_usefulness",
)
JUDGE_MAX_SEARCH_CALLS = 4
NONFATAL_DIAGNOSTICS = (
    "Skill descriptions were shortened to fit the 2% skills context budget.",
)
USAGE_LIMIT_RE = re.compile(
    r"(?:you(?:'|’)?ve hit your usage limit|usage limit.*"
    r"(?:purchase more credits|try again))",
    re.IGNORECASE,
)
INFRASTRUCTURE_FAILURE_KINDS = frozenset({"usage_limit"})


class BenchmarkError(RuntimeError):
    """Raised for a benchmark contract or execution failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def command_output(args: Sequence[str], cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BenchmarkError(f"command failed ({' '.join(args)}): {detail}")
    return result.stdout.strip()


def git_commit(repo_root: Path) -> str:
    return command_output(["git", "rev-parse", "HEAD"], repo_root)


def installed_plugins(codex: str, cwd: Path) -> tuple[dict[str, Any], ...]:
    payload = load_json_from_text(
        command_output([codex, "plugin", "list", "--json"], cwd),
        source="codex plugin list --json",
    )
    records = payload.get("installed") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise BenchmarkError("Codex plugin inventory has no `installed` array")
    return tuple(
        record
        for record in records
        if isinstance(record, dict)
        and record.get("installed") is True
        and record.get("enabled") is True
        and isinstance(record.get("pluginId"), str)
    )


def load_json_from_text(text: str, *, source: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BenchmarkError(f"cannot parse JSON from {source}: {exc}") from exc


def external_skill_paths(
    plugin_records: Sequence[dict[str, Any]],
) -> tuple[Path, ...]:
    """Find non-system skills that must be disabled in both benchmark arms."""
    personal_roots = (
        Path.home() / ".agents" / "skills",
        Path.home() / ".codex" / "skills",
    )
    candidates: set[Path] = set()
    for root in personal_roots:
        if not root.is_dir():
            continue
        for path in root.glob("**/SKILL.md"):
            if ".system" not in path.parts and path.is_file():
                candidates.add(path.resolve())
    for record in plugin_records:
        source = record.get("source")
        raw_path = source.get("path") if isinstance(source, dict) else None
        if not isinstance(raw_path, str):
            continue
        plugin_root = Path(raw_path)
        if plugin_root.is_dir():
            candidates.update(
                path.resolve()
                for path in plugin_root.glob("**/SKILL.md")
                if path.is_file()
            )
    return tuple(
        sorted(candidates, key=str)
    )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=str):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def ensure_clean_repo(repo_root: Path) -> None:
    status = command_output(["git", "status", "--porcelain"], repo_root)
    if status:
        raise BenchmarkError("benchmark runner requires a clean repository worktree")


def load_evals(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("evals"), list):
        raise BenchmarkError("evals file must contain an `evals` array")
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in payload["evals"]:
        if not isinstance(raw, dict):
            raise BenchmarkError("each eval must be an object")
        eval_id = raw.get("id")
        if not isinstance(eval_id, int) or eval_id in seen:
            raise BenchmarkError("eval ids must be unique integers")
        for key in ("name", "mode", "prompt", "expected_output", "expectations"):
            if key not in raw:
                raise BenchmarkError(f"eval {eval_id} missing `{key}`")
        if raw["mode"] not in {"standard", "strict"}:
            raise BenchmarkError(f"eval {eval_id} mode must be standard or strict")
        if not isinstance(raw["expectations"], list):
            raise BenchmarkError(f"eval {eval_id} expectations must be an array")
        seen.add(eval_id)
        result.append(raw)
    return result


def disabled_skill_override(paths: Sequence[Path]) -> str:
    entries = [
        {"path": str(path), "enabled": False}
        for path in paths
        if path.is_file()
    ]
    inline = ",".join(
        "{path=" + json.dumps(entry["path"]) + ",enabled=false}" for entry in entries
    )
    return f"skills.config=[{inline}]"


def codex_base_args(
    *,
    codex: str,
    model: str,
    project: Path,
    sandbox: str,
    search: bool,
    disabled_plugins: Sequence[str],
    disabled_skills: Sequence[Path],
) -> list[str]:
    physical_project = project.resolve()
    args = [codex]
    if search:
        args.append("--search")
    args.extend(
        [
            "-a",
            "never",
            "-s",
            sandbox,
            "-m",
            model,
            "-C",
            str(physical_project),
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
        ]
    )
    for plugin_id in disabled_plugins:
        args.extend(["-c", f'plugins.{json.dumps(plugin_id)}.enabled=false'])
    args.extend(
        [
            "-c",
            disabled_skill_override(disabled_skills),
            "-c",
            f'projects.{json.dumps(str(physical_project))}.trust_level="trusted"',
        ]
    )
    return args


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_streamed_process(
    args: Sequence[str],
    *,
    cwd: Path,
    stdin_text: str,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> tuple[int, bool, float]:
    started = time.monotonic()
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            process.communicate(stdin_text, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_group(process)
        returncode = process.returncode if process.returncode is not None else 124
    return returncode, timed_out, time.monotonic() - started


def parse_jsonl_metrics(path: Path) -> dict[str, Any]:
    usage = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    thread_id = ""
    item_types: Counter[str] = Counter()
    errors: list[str] = []
    warnings: list[str] = []
    malformed = 0

    def record_diagnostic(message: str) -> None:
        target = (
            warnings
            if any(message.startswith(prefix) for prefix in NONFATAL_DIAGNOSTICS)
            else errors
        )
        if message not in target:
            target.append(message)

    if not path.is_file():
        return {
            "thread_id": thread_id,
            "usage": usage,
            "total_tokens": 0,
            "item_types": {},
            "tool_item_types": {},
            "total_tool_calls": 0,
            "errors": ["transcript missing"],
            "warnings": [],
            "malformed_jsonl_lines": 0,
        }
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or "")
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            for key in usage:
                value = event["usage"].get(key)
                if isinstance(value, int):
                    usage[key] = value
        if event.get("type") == "error":
            record_diagnostic(str(event.get("message") or "unknown Codex error"))
        if event.get("type") == "turn.failed":
            failure = event.get("error")
            if isinstance(failure, dict):
                record_diagnostic(str(failure.get("message") or "unknown Codex error"))
            elif failure:
                record_diagnostic(str(failure))
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict):
            item_type = str(item.get("type") or "unknown")
            item_types[item_type] += 1
            if item_type == "error":
                record_diagnostic(str(item.get("message") or "unknown Codex error"))
    tool_item_types = {
        key: value
        for key, value in sorted(item_types.items())
        if key in TOOL_ITEM_TYPES or key.endswith("_tool_call")
    }
    return {
        "thread_id": thread_id,
        "usage": usage,
        # cached_input_tokens and reasoning_output_tokens are breakdowns of
        # input_tokens and output_tokens, not additional tokens.
        "total_tokens": usage["input_tokens"] + usage["output_tokens"],
        "item_types": dict(sorted(item_types.items())),
        "tool_item_types": tool_item_types,
        "total_tool_calls": sum(tool_item_types.values()),
        "errors": errors,
        "warnings": warnings,
        "malformed_jsonl_lines": malformed,
    }


def execution_failure_kind(
    *,
    returncode: int,
    timed_out: bool,
    transcript_metrics: dict[str, Any],
) -> str | None:
    errors = transcript_metrics.get("errors")
    messages = "\n".join(str(item) for item in errors) if isinstance(errors, list) else ""
    if USAGE_LIMIT_RE.search(messages):
        return "usage_limit"
    if timed_out:
        return "timeout"
    if returncode != 0:
        return "process_error"
    if messages:
        return "transcript_error"
    return None


def copy_research_outputs(project: Path, outputs: Path) -> dict[str, Any]:
    sessions = sorted(
        project.glob("RESEARCH/*/state.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not sessions:
        return {}
    session = sessions[-1].parent
    copied: list[str] = []
    for source in (
        *sorted((session / "outputs").glob("*.md")),
        session / "outputs" / "verification_report.json",
        session / "outputs" / "eval_report.json",
        session / "artifacts" / "merge_report.json",
        session / "state.json",
    ):
        if not source.is_file():
            continue
        relative_name = f"research-{source.name}"
        destination = outputs / relative_name
        shutil.copy2(source, destination)
        copied.append(relative_name)
    state = load_json(session / "state.json")
    return {
        "session_path": str(session),
        "state": state if isinstance(state, dict) else {},
        "copied_files": copied,
    }


def primary_report(outputs: Path) -> tuple[Path | None, str]:
    """Return the user-facing research deliverable, excluding internal audits."""
    for name in PRIMARY_REPORT_NAMES:
        path = outputs / name
        if path.is_file():
            return path, path.read_text(encoding="utf-8", errors="replace")
    return None, ""


def unique_urls(text: str) -> list[str]:
    cleaned = {
        match.rstrip(".,;:")
        for match in URL_RE.findall(text)
        if match.startswith(("http://", "https://"))
    }
    return sorted(cleaned)


def domains(urls: Iterable[str]) -> list[str]:
    result = {
        (urlsplit(url).hostname or "").lower().removeprefix("www.")
        for url in urls
    }
    return sorted(domain for domain in result if domain)


def pattern_passed(corpus: str, patterns: Sequence[str]) -> bool:
    return any(re.search(pattern, corpus, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def deterministic_grade(
    *,
    eval_case: dict[str, Any],
    run_dir: Path,
    execution: dict[str, Any],
    research: dict[str, Any],
) -> dict[str, Any]:
    outputs = run_dir / "outputs"
    primary_path, corpus = primary_report(outputs)
    urls = unique_urls(corpus)
    unique_domains = domains(urls)
    expectations: list[dict[str, Any]] = [
        {
            "text": "The Codex process completed successfully without transcript errors.",
            "passed": execution["returncode"] == 0
            and not execution["timed_out"]
            and not execution["transcript_metrics"]["errors"],
            "evidence": (
                f"returncode={execution['returncode']}, timed_out={execution['timed_out']}, "
                f"errors={len(execution['transcript_metrics']['errors'])}"
            ),
        },
        {
            "text": "The produced research corpus is substantive rather than a stub.",
            "passed": len(corpus.strip()) >= 1500,
            "evidence": f"research corpus characters={len(corpus.strip())}",
        },
        {
            "text": "The output exposes at least four inspectable source URLs.",
            "passed": len(urls) >= 4,
            "evidence": f"unique source URLs={len(urls)}",
        },
        {
            "text": "The exposed sources span at least two publisher domains.",
            "passed": len(unique_domains) >= 2,
            "evidence": f"unique domains={unique_domains}",
        },
        {
            "text": "The report explicitly discusses limitations, counter-evidence, or exceptions.",
            "passed": LIMIT_RE.search(corpus) is not None,
            "evidence": "limitation/counter-evidence language found"
            if LIMIT_RE.search(corpus)
            else "no limitation/counter-evidence language found",
        },
    ]
    for expected in eval_case["expectations"]:
        patterns = expected.get("patterns") if isinstance(expected, dict) else []
        patterns = [str(item) for item in patterns] if isinstance(patterns, list) else []
        passed = bool(patterns) and pattern_passed(corpus, patterns)
        expectations.append(
            {
                "text": str(expected.get("text") or "task-specific expectation"),
                "passed": passed,
                "evidence": f"matched one of {patterns}" if passed else f"matched none of {patterns}",
            }
        )
    passed_count = sum(1 for item in expectations if item["passed"])
    state = research.get("state") if isinstance(research.get("state"), dict) else {}
    auditability = {
        "research_session_created": bool(research),
        "phase": state.get("phase"),
        "status": state.get("status"),
        "verification_passed": bool((state.get("verification") or {}).get("passed"))
        if isinstance(state.get("verification"), dict)
        else False,
        "evaluation_passed": bool((state.get("evaluation") or {}).get("passed"))
        if isinstance(state.get("evaluation"), dict)
        else False,
    }
    result = {
        "expectations": expectations,
        "summary": {
            "passed": passed_count,
            "failed": len(expectations) - passed_count,
            "total": len(expectations),
            "pass_rate": round(passed_count / len(expectations), 6),
        },
        "execution_metrics": {
            "tool_calls": execution["transcript_metrics"]["tool_item_types"],
            "total_tool_calls": execution["transcript_metrics"]["total_tool_calls"],
            "errors_encountered": len(execution["transcript_metrics"]["errors"]),
            "output_chars": len(corpus),
            "source_urls": len(urls),
            "source_domains": len(unique_domains),
            "primary_report": primary_path.name if primary_path else None,
        },
        "timing": {
            "executor_duration_seconds": execution["duration_seconds"],
            "total_tokens": execution["transcript_metrics"]["total_tokens"],
        },
        "claims": [],
        "user_notes_summary": {
            "uncertainties": [],
            "needs_review": execution["transcript_metrics"]["errors"],
            "workarounds": [],
        },
        "eval_feedback": {
            "suggestions": [],
            "overall": "Deterministic checks are complemented by a blinded model judge.",
        },
        "auditability": auditability,
        "source_urls": urls,
        "source_domains": unique_domains,
    }
    write_json(run_dir / "grading.json", result)
    return result


def prepare_project(repo_root: Path, run_dir: Path, configuration: str) -> Path:
    project = run_dir / "project"
    project.mkdir(parents=True, exist_ok=True)
    command_output(["git", "init", "-q"], project)
    if configuration == "with_skill":
        install_log = run_dir / "install.log"
        result = subprocess.run(
            [
                "sh",
                str(repo_root / "install.sh"),
                "--scope",
                "project",
                "--project-root",
                str(project),
            ],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        write_text(install_log, result.stdout)
        if result.returncode != 0:
            raise BenchmarkError(
                f"project-local install failed for {run_dir}: {result.stdout.strip()}"
            )
    return project


def prepare_eval_inputs(iteration: Path, eval_case: dict[str, Any]) -> None:
    """Create files shared by both arms before concurrent execution starts."""
    eval_dir = iteration / str(eval_case["name"])
    write_json(
        eval_dir / "eval_metadata.json",
        {
            "eval_id": eval_case["id"],
            "eval_name": eval_case["name"],
            "prompt": eval_case["prompt"],
            "assertions": [item["text"] for item in eval_case["expectations"]],
        },
    )
    write_text(eval_dir / "prompt.txt", str(eval_case["prompt"]) + "\n")


def validate_resume_metadata(
    existing: dict[str, Any],
    current: dict[str, Any],
) -> None:
    keys = (
        "repo_root",
        "candidate_skill_tree_sha256",
        "model",
        "codex",
        "codex_version",
        "evals_path",
        "eval_ids",
        "configurations",
        "baseline_isolation",
    )
    mismatches = [key for key in keys if existing.get(key) != current.get(key)]
    if mismatches:
        raise BenchmarkError(
            "cannot resume because benchmark contract changed: "
            + ", ".join(mismatches)
        )


def archive_run_attempt(run_dir: Path) -> Path | None:
    if not run_dir.is_dir() or not any(run_dir.iterdir()):
        return None
    attempts = run_dir / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    index = 1
    while (attempts / f"attempt-{index}").exists():
        index += 1
    archive = attempts / f"attempt-{index}"
    archive.mkdir()
    for child in tuple(run_dir.iterdir()):
        if child == attempts:
            continue
        shutil.move(str(child), archive / child.name)
    return archive


def successful_execution(run_dir: Path) -> bool:
    execution_path = run_dir / "execution.json"
    if not execution_path.is_file():
        return False
    execution = load_json(execution_path)
    if not isinstance(execution, dict):
        return False
    metrics = parse_jsonl_metrics(run_dir / "transcript.jsonl")
    failure_kind = execution_failure_kind(
        returncode=int(execution.get("returncode", 1)),
        timed_out=bool(execution.get("timed_out")),
        transcript_metrics=metrics,
    )
    execution["transcript_metrics"] = metrics
    execution["failure_kind"] = failure_kind
    write_json(execution_path, execution)
    return failure_kind is None


def run_one(
    *,
    repo_root: Path,
    iteration: Path,
    eval_case: dict[str, Any],
    configuration: str,
    codex: str,
    model: str,
    timeout_seconds: int,
    disabled_plugins: Sequence[str],
    disabled_skills: Sequence[Path],
) -> dict[str, Any]:
    eval_dir = iteration / str(eval_case["name"])
    run_dir = eval_dir / configuration
    outputs = run_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    project = prepare_project(repo_root, run_dir, configuration)
    final_path = outputs / "final.md"
    transcript_path = run_dir / "transcript.jsonl"
    stderr_path = run_dir / "stderr.log"
    args = codex_base_args(
        codex=codex,
        model=model,
        project=project,
        sandbox="workspace-write",
        search=True,
        disabled_plugins=disabled_plugins,
        disabled_skills=disabled_skills,
    )
    args.extend(
        [
            "--json",
            "--output-last-message",
            str(final_path),
            "-",
        ]
    )
    returncode, timed_out, duration = run_streamed_process(
        args,
        cwd=project,
        stdin_text=str(eval_case["prompt"]),
        stdout_path=transcript_path,
        stderr_path=stderr_path,
        timeout_seconds=timeout_seconds,
    )
    transcript_metrics = parse_jsonl_metrics(transcript_path)
    failure_kind = execution_failure_kind(
        returncode=returncode,
        timed_out=timed_out,
        transcript_metrics=transcript_metrics,
    )
    execution = {
        "configuration": configuration,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 6),
        "transcript_metrics": transcript_metrics,
        "failure_kind": failure_kind,
        "command": args,
    }
    write_json(run_dir / "execution.json", execution)
    write_json(
        run_dir / "timing.json",
        {
            "total_tokens": transcript_metrics["total_tokens"],
            "duration_ms": round(duration * 1000),
            "total_duration_seconds": round(duration, 6),
        },
    )
    research = copy_research_outputs(project, outputs)
    grading = deterministic_grade(
        eval_case=eval_case,
        run_dir=run_dir,
        execution=execution,
        research=research,
    )
    write_json(
        outputs / "metrics.json",
        {
            "tool_calls": transcript_metrics["tool_item_types"],
            "total_tool_calls": transcript_metrics["total_tool_calls"],
            "files_created": sorted(
                str(path.relative_to(project))
                for path in project.rglob("*")
                if path.is_file() and ".git" not in path.parts
            ),
            "errors_encountered": len(transcript_metrics["errors"]),
            "output_chars": grading["execution_metrics"]["output_chars"],
            "transcript_chars": transcript_path.stat().st_size
            if transcript_path.is_file()
            else 0,
        },
    )
    return {
        "eval_id": eval_case["id"],
        "eval_name": eval_case["name"],
        "configuration": configuration,
        "returncode": returncode,
        "failure_kind": failure_kind,
        "pass_rate": grading["summary"]["pass_rate"],
    }


def run_benchmark(args: argparse.Namespace) -> Path:
    repo_root = args.repo_root.resolve()
    ensure_clean_repo(repo_root)
    evals = load_evals(args.evals)
    workspace = args.workspace.resolve()
    iteration = workspace / args.iteration
    iteration.mkdir(parents=True, exist_ok=True)
    plugin_records = installed_plugins(args.codex, repo_root)
    disabled_plugins = tuple(
        sorted(str(record["pluginId"]) for record in plugin_records)
    )
    disabled_skills = external_skill_paths(plugin_records)
    current_metadata = {
        "created_at": utc_now(),
        "repo_root": str(repo_root),
        "repo_commit": git_commit(repo_root),
        "candidate_skill_tree_sha256": tree_digest(
            repo_root / "skills" / "insane-research"
        ),
        "model": args.model,
        "codex": args.codex,
        "codex_version": command_output([args.codex, "--version"], repo_root),
        "evals_path": str(args.evals.resolve()),
        "eval_ids": [item["id"] for item in evals],
        "configurations": list(CONFIGURATIONS),
        "baseline_isolation": {
            "ignore_user_config": True,
            "ignore_rules": True,
            "disabled_plugins": list(disabled_plugins),
            "disabled_skill_paths": [str(path) for path in disabled_skills],
            "system_skills_retained": True,
            "codex_home_changed": False,
        },
    }
    metadata_path = iteration / "run_metadata.json"
    if args.resume:
        if not metadata_path.is_file():
            raise BenchmarkError(
                f"cannot resume without benchmark metadata: {metadata_path}"
            )
        metadata = load_json(metadata_path)
        if not isinstance(metadata, dict):
            raise BenchmarkError(f"invalid benchmark metadata: {metadata_path}")
        validate_resume_metadata(metadata, current_metadata)
        history = metadata.setdefault("resume_history", [])
        if not isinstance(history, list):
            raise BenchmarkError("invalid benchmark metadata: resume_history must be an array")
        history.append(
            {
                "resumed_at": utc_now(),
                "repo_commit": current_metadata["repo_commit"],
            }
        )
        write_json(metadata_path, metadata)
    else:
        metadata = current_metadata
        write_json(metadata_path, metadata)
    for eval_case in evals:
        prepare_eval_inputs(iteration, eval_case)
    all_jobs = [
        (eval_case, configuration)
        for eval_case in evals
        for configuration in CONFIGURATIONS
    ]
    previous_results: dict[tuple[str, str], dict[str, Any]] = {}
    results_path = iteration / "run_results.json"
    if args.resume and results_path.is_file():
        raw_results = load_json(results_path)
        if isinstance(raw_results, list):
            previous_results = {
                (str(item.get("eval_name")), str(item.get("configuration"))): item
                for item in raw_results
                if isinstance(item, dict)
                and item.get("eval_name")
                and item.get("configuration")
            }
    jobs: list[tuple[dict[str, Any], str]] = []
    for eval_case, configuration in all_jobs:
        run_dir = iteration / str(eval_case["name"]) / configuration
        if args.resume and successful_execution(run_dir):
            continue
        if args.resume:
            archive_run_attempt(run_dir)
        jobs.append((eval_case, configuration))
    current_results: dict[tuple[str, str], dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                run_one,
                repo_root=repo_root,
                iteration=iteration,
                eval_case=eval_case,
                configuration=configuration,
                codex=args.codex,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                disabled_plugins=disabled_plugins,
                disabled_skills=disabled_skills,
            ): (eval_case["name"], configuration)
            for eval_case, configuration in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            eval_name, configuration = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - preserve other benchmark arms
                result = {
                    "eval_name": eval_name,
                    "configuration": configuration,
                    "error": str(exc),
                }
            current_results[(str(eval_name), str(configuration))] = result
            print(json.dumps(result, ensure_ascii=False), flush=True)
    results = []
    for eval_case, configuration in all_jobs:
        key = (str(eval_case["name"]), str(configuration))
        result = current_results.get(key) or previous_results.get(key)
        if result is None:
            result = {
                "eval_id": eval_case["id"],
                "eval_name": eval_case["name"],
                "configuration": configuration,
                "error": "missing benchmark result",
            }
        results.append(result)
    write_json(results_path, results)
    failures = [
        result
        for result in results
        if result.get("error") or result.get("returncode") != 0
    ]
    if failures:
        infrastructure = sum(
            result.get("failure_kind") in INFRASTRUCTURE_FAILURE_KINDS
            for result in failures
        )
        detail = (
            f" ({infrastructure} infrastructure interruption(s))"
            if infrastructure
            else ""
        )
        raise BenchmarkError(
            f"{len(failures)} benchmark arm(s) failed{detail}; "
            f"inspect {iteration / 'run_results.json'}"
        )
    return iteration


def refresh_derived_run_data(
    iteration: Path,
    evals: Sequence[dict[str, Any]],
) -> None:
    """Rebuild derived metrics from authoritative transcripts and outputs."""
    for eval_case in evals:
        eval_name = str(eval_case["name"])
        for configuration in CONFIGURATIONS:
            run_dir = iteration / eval_name / configuration
            execution_path = run_dir / "execution.json"
            if not execution_path.is_file():
                raise BenchmarkError(f"missing execution record: {execution_path}")
            execution = load_json(execution_path)
            if not isinstance(execution, dict):
                raise BenchmarkError(f"invalid execution record: {execution_path}")
            transcript_path = run_dir / "transcript.jsonl"
            transcript_metrics = parse_jsonl_metrics(transcript_path)
            execution["transcript_metrics"] = transcript_metrics
            execution["failure_kind"] = execution_failure_kind(
                returncode=int(execution.get("returncode", 1)),
                timed_out=bool(execution.get("timed_out")),
                transcript_metrics=transcript_metrics,
            )
            write_json(execution_path, execution)
            duration = float(execution.get("duration_seconds") or 0)
            write_json(
                run_dir / "timing.json",
                {
                    "total_tokens": transcript_metrics["total_tokens"],
                    "duration_ms": round(duration * 1000),
                    "total_duration_seconds": duration,
                },
            )
            outputs = run_dir / "outputs"
            state_path = outputs / "research-state.json"
            research = {"state": load_json(state_path)} if state_path.is_file() else {}
            grading = deterministic_grade(
                eval_case=eval_case,
                run_dir=run_dir,
                execution=execution,
                research=research,
            )
            metrics_path = outputs / "metrics.json"
            metrics = load_json(metrics_path) if metrics_path.is_file() else {}
            if not isinstance(metrics, dict):
                metrics = {}
            metrics.update(
                {
                    "tool_calls": transcript_metrics["tool_item_types"],
                    "total_tool_calls": transcript_metrics["total_tool_calls"],
                    "errors_encountered": len(transcript_metrics["errors"]),
                    "warnings_encountered": len(transcript_metrics["warnings"]),
                    "output_chars": grading["execution_metrics"]["output_chars"],
                    "transcript_chars": transcript_path.stat().st_size,
                }
            )
            write_json(metrics_path, metrics)


def read_run_output(run_dir: Path, max_chars: int = 60000) -> str:
    _path, corpus = primary_report(run_dir / "outputs")
    corpus = corpus.strip()
    if len(corpus) <= max_chars:
        return corpus
    return corpus[:max_chars] + "\n\n[output truncated by benchmark judge]"


def stable_blind_mapping(eval_name: str, commit: str) -> dict[str, str]:
    seed = int(hashlib.sha256(f"{commit}:{eval_name}".encode()).hexdigest()[:16], 16)
    randomizer = random.Random(seed)
    configurations = list(CONFIGURATIONS)
    randomizer.shuffle(configurations)
    return {"A": configurations[0], "B": configurations[1]}


def judge_prompt(
    *,
    eval_case: dict[str, Any],
    mapping: dict[str, str],
    eval_dir: Path,
) -> str:
    expected = "\n".join(f"- {item['text']}" for item in eval_case["expectations"])
    outputs: dict[str, str] = {}
    summaries: dict[str, Any] = {}
    for label, configuration in mapping.items():
        outputs[label] = read_run_output(eval_dir / configuration)
        grading = load_json(eval_dir / configuration / "grading.json")
        summaries[label] = {
            key: grading[key]
            for key in ("expectations", "summary", "execution_metrics")
            if key in grading
        }
    return f"""You are a blind evaluator. Compare output A and output B without trying to infer
which system produced either output. Judge only how well each output fulfills the original
research task.

Prioritize, in order:
1. factual correctness and whether conclusions are proportionate to the cited evidence;
2. completeness against the requested scope;
3. source quality, citation traceability, and independence;
4. honest treatment of counter-evidence, uncertainty, and unresolved points;
5. decision usefulness and readable structure.

Score every dimension and `overall` on the same scale:
- 1 = unacceptable
- 2 = weak
- 3 = adequate
- 4 = strong
- 5 = excellent

The overall score must be a holistic 1-to-5 quality score consistent with the dimension scores.
Do not award points merely for being longer or for claiming that an audit passed. Treat the
deterministic summaries as secondary evidence. If a citation cannot be checked from the supplied
material, use live web search to spot-check decisive disputed or time-sensitive claims from both
outputs under the same standard. Prefer official primary sources and use no more than
{JUDGE_MAX_SEARCH_CALLS} search/discovery calls total. Be decisive, but use TIE when genuinely
equivalent.

ORIGINAL TASK
{eval_case['prompt']}

EXPECTED COVERAGE
{expected}

OUTPUT A
{outputs['A']}

DETERMINISTIC SUMMARY A
{json.dumps(summaries['A'], ensure_ascii=False)}

OUTPUT B
{outputs['B']}

DETERMINISTIC SUMMARY B
{json.dumps(summaries['B'], ensure_ascii=False)}
"""


def judge_score_contract_valid(comparison: dict[str, Any]) -> bool:
    scores = comparison.get("scores")
    if not isinstance(scores, dict):
        return False
    for label in ("A", "B"):
        score = scores.get(label)
        if not isinstance(score, dict):
            return False
        dimensions = [score.get(name) for name in JUDGE_DIMENSIONS]
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 5
            for value in dimensions
        ):
            return False
        overall = score.get("overall")
        if (
            isinstance(overall, bool)
            or not isinstance(overall, (int, float))
            or not 1 <= float(overall) <= 5
        ):
            return False
        if abs(float(overall) - statistics.mean(dimensions)) > 1:
            return False
    return True


def judge_one(
    *,
    iteration: Path,
    eval_case: dict[str, Any],
    commit: str,
    codex: str,
    model: str,
    timeout_seconds: int,
    disabled_plugins: Sequence[str],
    disabled_skills: Sequence[Path],
) -> dict[str, Any]:
    eval_dir = iteration / str(eval_case["name"])
    mapping = stable_blind_mapping(str(eval_case["name"]), commit)
    judge_dir = eval_dir / "blind_judge"
    project = judge_dir / "project"
    project.mkdir(parents=True, exist_ok=True)
    command_output(["git", "init", "-q"], project)
    final_path = judge_dir / "comparison.json"
    transcript_path = judge_dir / "transcript.jsonl"
    stderr_path = judge_dir / "stderr.log"
    args = codex_base_args(
        codex=codex,
        model=model,
        project=project,
        sandbox="read-only",
        search=True,
        disabled_plugins=disabled_plugins,
        disabled_skills=disabled_skills,
    )
    args.extend(
        [
            "--json",
            "--output-schema",
            str(JUDGE_SCHEMA.resolve()),
            "--output-last-message",
            str(final_path),
            "-",
        ]
    )
    returncode, timed_out, duration = run_streamed_process(
        args,
        cwd=project,
        stdin_text=judge_prompt(eval_case=eval_case, mapping=mapping, eval_dir=eval_dir),
        stdout_path=transcript_path,
        stderr_path=stderr_path,
        timeout_seconds=timeout_seconds,
    )
    comparison: dict[str, Any] = {}
    if final_path.is_file():
        loaded = load_json(final_path)
        comparison = loaded if isinstance(loaded, dict) else {}
    winner = str(comparison.get("winner") or "")
    winner_configuration = mapping.get(winner) if winner in {"A", "B"} else "TIE"
    result = {
        "eval_id": eval_case["id"],
        "eval_name": eval_case["name"],
        "mapping": mapping,
        "winner": winner,
        "winner_configuration": winner_configuration,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 6),
        "comparison": comparison,
        "score_contract_valid": judge_score_contract_valid(comparison),
        "transcript_metrics": parse_jsonl_metrics(transcript_path),
    }
    write_json(judge_dir / "unblinded.json", result)
    return result


def judge_benchmark(args: argparse.Namespace) -> Path:
    iteration = args.workspace.resolve() / args.iteration
    metadata = load_json(iteration / "run_metadata.json")
    evals = load_evals(args.evals)
    refresh_derived_run_data(iteration, evals)
    commit = str(metadata.get("repo_commit") or "")
    isolation = metadata.get("baseline_isolation")
    if not isinstance(isolation, dict):
        raise BenchmarkError("run metadata has no baseline isolation record")
    disabled_plugins = tuple(
        str(item) for item in isolation.get("disabled_plugins", [])
    )
    disabled_skills = tuple(
        Path(str(item)) for item in isolation.get("disabled_skill_paths", [])
    )
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.judge_workers) as executor:
        futures = {
            executor.submit(
                judge_one,
                iteration=iteration,
                eval_case=eval_case,
                commit=commit,
                codex=args.codex,
                model=args.judge_model or args.model,
                timeout_seconds=args.judge_timeout_seconds,
                disabled_plugins=disabled_plugins,
                disabled_skills=disabled_skills,
            ): eval_case["name"]
            for eval_case in evals
        }
        for future in concurrent.futures.as_completed(futures):
            eval_name = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = {"eval_name": eval_name, "error": str(exc)}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    write_json(iteration / "judge_results.json", results)
    failures = [
        result
        for result in results
        if result.get("error")
        or result.get("returncode") != 0
        or result.get("winner") not in {"A", "B", "TIE"}
        or result.get("score_contract_valid") is not True
    ]
    if failures:
        raise BenchmarkError(
            f"{len(failures)} judge run(s) failed; inspect {iteration / 'judge_results.json'}"
        )
    return iteration


def stat(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": round(statistics.mean(values), 6),
        "stddev": round(statistics.pstdev(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def score_for_configuration(
    comparison_result: dict[str, Any], configuration: str
) -> float | None:
    mapping = comparison_result.get("mapping")
    comparison = comparison_result.get("comparison")
    if not isinstance(mapping, dict) or not isinstance(comparison, dict):
        return None
    label = next((key for key, value in mapping.items() if value == configuration), None)
    scores = comparison.get("scores")
    if label is None or not isinstance(scores, dict) or not isinstance(scores.get(label), dict):
        return None
    value = scores[label].get("overall")
    return float(value) if isinstance(value, (int, float)) else None


def aggregate_benchmark(args: argparse.Namespace) -> Path:
    iteration = args.workspace.resolve() / args.iteration
    metadata = load_json(iteration / "run_metadata.json")
    evals = load_evals(args.evals)
    refresh_derived_run_data(iteration, evals)
    judge_results_raw = load_json(iteration / "judge_results.json")
    judge_results = {
        str(item.get("eval_name")): item
        for item in judge_results_raw
        if isinstance(item, dict) and item.get("eval_name")
    }
    runs: list[dict[str, Any]] = []
    values: dict[str, dict[str, list[float]]] = {
        configuration: {
            "pass_rate": [],
            "time_seconds": [],
            "tokens": [],
            "quality_score": [],
        }
        for configuration in CONFIGURATIONS
    }
    audit_passes = 0
    for eval_case in evals:
        eval_name = str(eval_case["name"])
        comparison_result = judge_results.get(eval_name, {})
        for configuration in CONFIGURATIONS:
            run_dir = iteration / eval_name / configuration
            grading = load_json(run_dir / "grading.json")
            timing = load_json(run_dir / "timing.json")
            metrics = load_json(run_dir / "outputs" / "metrics.json")
            quality_score = score_for_configuration(comparison_result, configuration)
            result = {
                "pass_rate": float(grading["summary"]["pass_rate"]),
                "passed": int(grading["summary"]["passed"]),
                "failed": int(grading["summary"]["failed"]),
                "total": int(grading["summary"]["total"]),
                "time_seconds": float(timing["total_duration_seconds"]),
                "tokens": int(timing["total_tokens"]),
                "tool_calls": int(metrics["total_tool_calls"]),
                "errors": int(metrics["errors_encountered"]),
                "quality_score": quality_score,
            }
            runs.append(
                {
                    "eval_id": eval_case["id"],
                    "eval_name": eval_name,
                    "configuration": configuration,
                    "run_number": 1,
                    "result": result,
                    "expectations": grading["expectations"],
                    "notes": [],
                }
            )
            for metric in ("pass_rate", "time_seconds", "tokens"):
                values[configuration][metric].append(float(result[metric]))
            if quality_score is not None:
                values[configuration]["quality_score"].append(quality_score)
            if configuration == "with_skill" and all(
                grading.get("auditability", {}).get(key)
                for key in ("research_session_created", "verification_passed", "evaluation_passed")
            ):
                audit_passes += 1
    summary: dict[str, Any] = {}
    for configuration in CONFIGURATIONS:
        summary[configuration] = {
            metric: stat(metric_values)
            for metric, metric_values in values[configuration].items()
        }
    summary["delta"] = {
        metric: round(
            summary["with_skill"][metric]["mean"]
            - summary["without_skill"][metric]["mean"],
            6,
        )
        for metric in ("pass_rate", "time_seconds", "tokens", "quality_score")
    }
    wins = Counter(
        str(result.get("winner_configuration") or "unknown")
        for result in judge_results.values()
    )
    notes = [
        (
            "Blind comparisons: "
            f"with_skill={wins.get('with_skill', 0)}, "
            f"without_skill={wins.get('without_skill', 0)}, "
            f"ties={wins.get('TIE', 0)}."
        ),
        (
            f"Audited phase-7 completion passed in {audit_passes}/{len(evals)} "
            "with-skill runs; this auditability metric is reported separately from "
            "the universal output pass rate."
        ),
        (
            "Positive time/token deltas mean the skill used more resources than baseline; "
            "interpret them together with blind quality and deterministic pass-rate deltas."
        ),
    ]
    benchmark = {
        "metadata": {
            "skill_name": "insane-research",
            "skill_path": str(ROOT / "skills" / "insane-research"),
            "executor_model": metadata.get("model"),
            "analyzer_model": args.judge_model or metadata.get("model"),
            "analyzer_web_search": True,
            "analyzer_search_call_limit": JUDGE_MAX_SEARCH_CALLS,
            "timestamp": utc_now(),
            "repo_commit": metadata.get("repo_commit"),
            "analyzer_repo_commit": git_commit(ROOT),
            "candidate_skill_tree_sha256": metadata.get(
                "candidate_skill_tree_sha256"
            ),
            "codex_version": metadata.get("codex_version"),
            "evals_run": [item["id"] for item in evals],
            "runs_per_configuration": 1,
            "baseline_isolation": metadata.get("baseline_isolation"),
        },
        "runs": runs,
        "run_summary": summary,
        "blind_comparisons": list(judge_results.values()),
        "notes": notes,
    }
    write_json(iteration / "benchmark.json", benchmark)
    write_text(iteration / "benchmark.md", benchmark_markdown(benchmark))
    return iteration


def markdown_number(value: Any, digits: int = 2) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def benchmark_markdown(benchmark: dict[str, Any]) -> str:
    summary = benchmark["run_summary"]
    lines = [
        "# Insane Research Codex benchmark",
        "",
        f"- Commit: `{benchmark['metadata'].get('repo_commit')}`",
        f"- Codex: `{benchmark['metadata'].get('codex_version')}`",
        f"- Executor: `{benchmark['metadata'].get('executor_model')}`",
        f"- Evaluations: {len(benchmark['metadata'].get('evals_run') or [])}",
        "",
        "## Aggregate",
        "",
        "| Metric | With skill | Base Codex | Delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in ("pass_rate", "quality_score", "time_seconds", "tokens"):
        lines.append(
            "| "
            + metric
            + " | "
            + markdown_number(summary["with_skill"][metric]["mean"])
            + " ± "
            + markdown_number(summary["with_skill"][metric]["stddev"])
            + " | "
            + markdown_number(summary["without_skill"][metric]["mean"])
            + " ± "
            + markdown_number(summary["without_skill"][metric]["stddev"])
            + " | "
            + markdown_number(summary["delta"][metric])
            + " |"
        )
    lines.extend(
        [
            "",
            "## Per evaluation",
            "",
            "| Eval | Configuration | Pass rate | Blind quality | Seconds | Tokens |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for run in benchmark["runs"]:
        result = run["result"]
        lines.append(
            f"| {run['eval_name']} | {run['configuration']} | "
            f"{markdown_number(result['pass_rate'])} | "
            f"{markdown_number(result.get('quality_score'))} | "
            f"{markdown_number(result['time_seconds'])} | {result['tokens']} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in benchmark["notes"])
    return "\n".join(lines) + "\n"


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--evals", type=Path, default=DEFAULT_EVALS)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--iteration", default="iteration-1")
    parser.add_argument("--codex", default=shutil.which("codex") or "codex")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--judge-timeout-seconds", type=int, default=600)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--judge-workers", type=int, default=3)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="preserve successful arms and rerun only missing or failed arms",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "judge", "report", "all"):
        subparser = subparsers.add_parser(name)
        add_common_arguments(subparser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"run", "all"}:
            iteration = run_benchmark(args)
            print(f"run workspace: {iteration}")
        if args.command in {"judge", "all"}:
            iteration = judge_benchmark(args)
            print(f"judge workspace: {iteration}")
        if args.command in {"report", "all"}:
            iteration = aggregate_benchmark(args)
            print(f"benchmark JSON: {iteration / 'benchmark.json'}")
            print(f"benchmark Markdown: {iteration / 'benchmark.md'}")
    except BenchmarkError as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
