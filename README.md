# insane-research-codex

A Codex-native derivative of `fivetaku/insane-research` 2.8.2. It ports the upstream research architecture to Codex skill discovery, custom subagents, provider-neutral retrieval, deterministic claim verification, and a final report audit.

> This is a clean derivative, not a byte-for-byte upstream mirror. The environment used for the port could inspect the public GitHub source but could not perform a normal `git clone`. See `UPSTREAM.md` for the exact inspected commit and provenance.

## What changed

- Repo skill at `.agents/skills/insane-research/`
- Plugin skill at `skills/insane-research/` with `.codex-plugin/plugin.json`
- Read-only Codex custom agents in `.codex/agents/`
- No Claude-specific commands, environment variables, or permission modes
- No automatic stars, telemetry, or first-run network side effects
- Provider-neutral use of the web, browser, repositories, files, academic tools, and user-configured MCP servers
- One standard-library CLI for sessions, merge, verification, and report audit
- Source-family independence, strict mode, counter-searches, primary-source checks, executable proof, signed verification state, and unresolved/refuted leakage checks

## 3.1 reliability hardening

- A standalone report audit recomputes the verification signature and rejects any source registry, claim ledger, or status-output change made after validation.
- Supporting evidence (`source_urls`) and defeating counter-evidence (`counter_source_urls`) are stored separately. A supporting source can no longer be reused as the sole proof that a claim was refuted.
- Strict high-risk verification requires three independent source families and at least two A/B-grade families.
- Executable proof requires command, output, environment/version metadata, and verdict.
- Report coverage counts a verified claim only when the claim itself and an adjacent supporting source marker appear together.
- Source URL normalization accepts only HTTP(S), rejects embedded credentials, and safely preserves IPv6 hosts.
- Release metadata is generated and checked for both hash mismatches and unlisted distributable files.
- GitHub Actions runs the standard-library test and integrity suite across Python 3.9, 3.11, and 3.14.

### Upgrading existing 3.0 sessions

Existing 3.0 session directories can be retained, but claims with `counter_refuted: true` do not yet have separate `counter_source_urls`. Under 3.1 those claims may become `unresolved` or a process violation until defeating evidence is collected and recorded. Update only the affected entries in `artifacts/agent_returns.json`, then rerun `merge → validate → finalize`. Version 3.1 also strengthens the verification signature, so invalidating and regenerating prior `verification_report.json` and `eval_report.json` is expected.

## Install

User-wide:

```bash
./install.sh --scope user
```

Project-local:

```bash
./install.sh --scope project --project-root /path/to/project
```

PowerShell:

```powershell
./install.ps1 --scope user
```

Existing files are not overwritten unless `--force` is supplied; forced replacement creates backups.

## Use in Codex

```text
$insane-research Research the impact of AI coding agents on software productivity, with primary studies and counter-evidence.
```

The skill can also be selected implicitly for requests that clearly ask for deep or comprehensive research.

## Runtime workflow

```text
scope → plan 3–5 axes → parallel read-only subagents → parent merge
→ deterministic claim gate → verified-only synthesis → final report audit
```

Run the control utility directly from this repository:

```bash
./bin/insane-research doctor
./bin/insane-research schema
./bin/insane-research status --root RESEARCH
```

## Development checks

```bash
python3 -m compileall -q skills/insane-research/scripts
python3 -m unittest discover -s tests -v
python3 scripts/verify_package.py
python3 scripts/update_release_metadata.py --check
python3 scripts/verify_release.py
```

After an intentional release-file change, regenerate `MANIFEST.json` and `CHECKSUMS.sha256`, review the diff, and rerun the checks:

```bash
python3 scripts/update_release_metadata.py
python3 scripts/update_release_metadata.py --check
python3 scripts/verify_release.py
```

For the complete Korean guide, see `README.ko.md`. For attribution and design differences, see `NOTICE`, `UPSTREAM.md`, and `PORTING_NOTES.md`.

## License

MIT. Upstream copyright is preserved.
