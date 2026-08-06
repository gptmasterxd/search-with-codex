# Validation report

**Release:** 3.0.0-codex.1  
**Validated at:** 2026-08-06T12:40:40Z  
**Runtime used:** Python 3.13.5  
**Codex CLI in validation container:** not installed

## Results

- Python compilation: **PASS**
- Unit and integration tests: **PASS** — Ran 26 tests in 7.865s · OK
- Package integrity: **PASS** — PACKAGE CHECK: PASS · version: 3.0.0-codex.1 · skill files: 10 · custom agents: 5
- Project-local installer: **PASS**
- Installed-skill doctor check: **PASS**
- Installed custom-agent files: **5**
- End-to-end control flow (`init → merge → validate → finalize`): **PASS**

## Installed-skill doctor

```json
{
  "passed": true,
  "version": "3.0.0-codex.1",
  "checks": {
    "python": "3.13.5",
    "python_supported": true,
    "skill_root": "/tmp/tmpfxba8cpl/project/.agents/skills/insane-research",
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
  "checked_at": "2026-08-06T12:40:40Z",
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
  "leaks": [],
  "failures": []
}
```

## Verification record

```json
{
  "passed": true,
  "strict": false,
  "exit_code": 0,
  "signature": "74293d1d79446a107d62595a114b39decc1ab9dbf4e379c0e90936da2c02c9fd",
  "hard_errors": [],
  "process_violations": [],
  "counts": {
    "verified": 1,
    "unresolved": 0,
    "refuted": 0
  },
  "checked_at": "2026-08-06T12:40:40Z"
}
```

## What was not directly exercised

The container did not have the `codex` executable installed, so an interactive Codex session was not launched. Skill layout, plugin metadata, custom-agent TOML, install paths, Python 3.9 syntax compatibility, deterministic control flow, and installed-path execution were validated. Actual web-research quality still depends on the Codex model, enabled internet or MCP tools, source access, and the research prompt.
