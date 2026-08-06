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
python3 scripts/verify_release.py  # after release checksums are generated
```

For the complete Korean guide, see `README.ko.md`. For attribution and design differences, see `NOTICE`, `UPSTREAM.md`, and `PORTING_NOTES.md`.

## License

MIT. Upstream copyright is preserved.
