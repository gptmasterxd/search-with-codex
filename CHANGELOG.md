# Changelog

## 3.2.0 — 2026-08-07

### Added

- User-visible citation URL coverage metric and hard final-audit gate.
- Per-agent return directory with deterministic merge order and path-specific errors.
- Current-primary freshness sweeps for medical, legal, regulatory, standards, and fast-moving technical topics.
- Compact `brief` synthesis output to avoid replaying complete registries and status files into model context.
- Reviewed real-Codex benchmark harness and sanitized v3.1 baseline results.
- Validated Codex plugin author and interface metadata.
- Authority-aware `claim_scope` contract separating source-attributed facts from synthesized conclusions.
- Canonical-identifier checks for recent decision-changing primary records, including medical protocol/result reconciliation.

### Changed

- Standard planning defaults to 2–3 axes and at most three concurrent research agents; strict mode defaults to 3–4 axes and at most four.
- Per-axis discovery defaults are 6 standard / 8 strict calls, with compact decision-relevant return limits.
- Parent review starts from merge status and warnings, then inspects only targeted registry or ledger entries.
- Reports use linked source markers and omit self-certifying audit language from substantive findings.
- Session schema is now version 3; legacy aggregate agent returns remain supported.
- Strict synthesized high-risk claims require two independent A/B-grade families; a directly inspected authoritative source can verify only a visibly attributed, source-bound statement.
- Current technical adoption questions remain standard mode unless they are safety-, security-, financial-, or rights-critical; strict medical and legal work is unchanged.
- Per-axis returns default to six sources and four material claims, and reports use a decision-critical evidence subset instead of replaying the complete ledger.

### Fixed

- Removed concurrent patch contention on one shared `agent_returns.json`.
- Documented supported wait timeouts and bounded recovery from pre-thread spawn failures.
- Required the research-plan template to be read before patching.
- Enumerated valid claim types and clarified unresolved-claim placement to prevent avoidable merge warnings and audit retries.
- Scoped unresolved-claim fuzzy matching to local paragraphs so unrelated terms across a report cannot create a false leakage failure.
- Preserved accurately attributed study or authority results when broader evidence conflicts; disagreement now constrains the synthesized conclusion instead of erasing what each source reported.
- Required current medical comparison searches to include a date-bounded bibliographic route and registry/publication linkage, and required intervening legal measures to state their operative effect.
- Added one bounded, explicitly indirect sensitivity route for sparse exact-horizon or exact-comparator evidence, and required device/procedure research to cover mechanical and workflow failures.
- Kept unresolved/refuted annexes decision-facing instead of replaying internal claim IDs and status ledgers.

## 3.1.0 — 2026-08-06

### Fixed

- Recompute the verification signature during standalone report evaluation and reject stale source, ledger, or verified/unresolved/refuted outputs.
- Require `state.json`, `verification_report.json`, and the generated status-output counts to agree before a report audit can pass.
- Invalidate earlier verification and evaluation state whenever agent returns are merged again.
- Separate supporting evidence from defeating counter-evidence with `counter_source_urls` / `counter_source_ids`; supporting sources can no longer satisfy a refutation by themselves.
- Require `env` metadata for executable proof.
- Count verified-claim report coverage only when the claim and an adjacent supporting source marker are present together.
- Reject non-HTTP(S) source URLs and URLs containing embedded credentials; preserve bracketed IPv6 hosts during normalization.

### Changed

- Bumped session schema to version 2.
- Strict high-risk claims now require at least two independent A/B-grade source families in addition to three independent families overall.
- A standard refutation requires A/B/C counter-evidence; strict high-risk refutation requires A/B counter-evidence.
- Unified runtime, plugin, project, and release versions at `3.1.0`.

### Added

- Deterministic release metadata generator/checker with unlisted-file detection.
- GitHub Actions matrix for Python 3.9, 3.11, and 3.14, with third-party actions pinned to immutable commit SHAs.
- Dependabot updates for GitHub Actions.
- Regression coverage for stale signatures, status-output tampering, counter-evidence separation, strict source quality, executable environment metadata, URL schemes/IPv6, and adjacent report citations.

## 3.0.0-codex.1 — 2026-08-06

First Codex-native derivative based on upstream insane-research 2.8.2.

### Added

- Codex skill packaging and repository-scoped skill discovery
- Codex custom subagents for official, academic, web, adversarial verification, and report review roles
- provider-neutral retrieval instructions with prompt-injection boundaries
- `researchctl.py` session, merge, validate, evaluate, finalize, status, doctor, and schema commands
- source-family independence and conservative domain-grade normalization
- standard and strict high-risk claim gates
- executable-claim proof contract
- verification signature and report leakage/citation audit
- explicit user/project installer with preflight, backups, dry-run, and no hidden network side effects
- 26 deterministic tests and package integrity checks

### Removed from the upstream interaction model

- Claude-specific command and environment-variable dependencies
- automatic first-run setup and GitHub-star interaction
- shared-file writes by parallel research agents
- assumptions about a specific web-search provider
