# Validation report

**Release:** 3.1.0
**Validated at:** 2026-08-06T13:56:02Z
**Runtime used:** Python 3.13.5
**Codex CLI in validation container:** not installed

## Results

- Python compilation: **PASS**
- Python 3.9 grammar parse for runtime, release scripts, and tests: **PASS**
- Unit and integration tests: **PASS** — Ran 40 tests · OK
- Package integrity: **PASS** — PACKAGE CHECK: PASS · version: 3.1.0 · skill files: 10 · custom agents: 5
- Release metadata exact-set and checksum audit: **PASS** — 55 files
- Project-local installer: **PASS**
- Installed-skill doctor check: **PASS**
- Installed custom-agent files: **5**
- End-to-end control flow (`init → merge → validate → finalize`): **PASS**
- Git diff whitespace check: **PASS**

## Installed-skill doctor

```json
{
  "passed": true,
  "version": "3.1.0",
  "checks": {
    "python": "3.13.5",
    "python_supported": true,
    "skill_root": "<temporary-project>/.agents/skills/insane-research",
    "skill_md": true,
    "references": true,
    "templates": true,
    "cwd_writable": true
  }
}
```

## End-to-end gate metrics

```json
{
  "verdict": "PASS",
  "checked_at": "2026-08-06T13:56:02Z",
  "report_files": [
    "outputs/00_executive_summary.md",
    "outputs/01_full_report.md"
  ],
  "metrics": {
    "leak_rate": 0.0,
    "citation_resolution_rate": 1.0,
    "orphan_source_rate": 0.0,
    "verified_coverage_rate": 1.0
  },
  "counts": {
    "registered_sources": 2,
    "cited_sources": 2,
    "dangling_citations": 0,
    "orphan_sources": 0,
    "verified_claims": 1,
    "covered_verified_claims": 1,
    "leaked_claims": 0
  },
  "dangling_citations": [],
  "orphan_sources": [],
  "uncovered_verified_claims": [],
  "leaks": [],
  "failures": []
}
```

## Verification record

```json
{
  "passed": true,
  "checker_version": "3.1.0",
  "strict": false,
  "exit_code": 0,
  "signature": "282221b3262f94692c0f004ac1f89b8e48b1ad31ca01c62c88737e885fc7b42d",
  "hard_errors": [],
  "process_violations": [],
  "counts": {
    "verified": 1,
    "unresolved": 0,
    "refuted": 0
  },
  "checked_at": "2026-08-06T13:56:02Z"
}
```

## What was not directly exercised

The validation container did not have the `codex` executable installed, so an interactive Codex session was not launched. Skill layout, plugin metadata, custom-agent TOML, installation paths, Python 3.9 syntax compatibility, deterministic control flow, stale-signature rejection, release integrity, and installed-path execution were validated. Actual web-research quality still depends on the Codex model, enabled internet or MCP tools, source access, and the research prompt.
