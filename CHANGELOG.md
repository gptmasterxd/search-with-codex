# Changelog

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
