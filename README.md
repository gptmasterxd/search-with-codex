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

## 3.2 benchmark-driven improvements

- Every cited registry ID must expose its canonical URL in the user-facing report. Bare `[src_NNN]` markers now fail the final audit.
- Parallel results are saved as isolated `artifacts/agent_returns/*.json` files, removing the shared aggregate-file patch conflict while retaining legacy-session support.
- Current medical, legal, regulatory, standards, and fast-moving technical work includes a direct-primary freshness sweep over the cutoff date and preceding 24 months.
- Claims distinguish source-attributed facts from synthesized conclusions. A directly inspected A/B-grade authoritative origin can verify only a visibly attributed statement about what it says; synthesized strict conclusions still require two independent A/B-grade families.
- Recent decision-changing studies and official records must be opened by canonical identifier and checked for exact title, type, date, and result status. Registry linkage batches the identifier, quoted official title, and study metadata, and falls back to official machine-readable results where needed.
- Current technical adoption work stays in standard mode unless safety, security, finance, or fundamental rights make strict mode necessary. Per-axis returns are capped more tightly, and reports show a decision-critical evidence subset instead of dumping the complete ledger.
- Conflicting studies retain their accurately attributed results; only the cross-study synthesis remains unresolved. Legal freshness checks must identify the exact amended provision and its material effect.
- Sparse exact-window comparisons get one bounded sensitivity search for the nearest follow-up or an adjacent add-on/usual-care comparator, with indirectness kept explicit. Device and procedure reviews also cover mechanical and workflow failures.
- Standard mode starts with 2–3 axes and at most three research agents; strict mode starts with 3–4 axes and at most four. Per-axis search and return budgets are bounded.
- Merge review starts from compact warning output, and `researchctl brief` supplies one synthesis map instead of replaying the complete registry and ledger into model context.
- Human reports omit internal claim IDs and gate statuses, limit the evidence synthesis to six decision-critical findings, and summarize only decision-relevant gaps in the annexes.
- The plugin manifest now follows the validated Codex author and interface schema.

These changes address the reviewed [v3.1.0 versus base Codex benchmark](benchmarks/results/v3.1.0-vs-base.md), where v3.1 retained strong strict-mode currentness but used 4.69× the tokens of base Codex, exposed no usable links in one report, and missed a recent direct medical trial.

## 3.1 reliability hardening

- A standalone report audit recomputes the verification signature and rejects any source registry, claim ledger, or status-output change made after validation.
- Supporting evidence (`source_urls`) and defeating counter-evidence (`counter_source_urls`) are stored separately. A supporting source can no longer be reused as the sole proof that a claim was refuted.
- Strict high-risk verification requires three independent source families and at least two A/B-grade families.
- Executable proof requires command, output, environment/version metadata, and verdict.
- Report coverage counts a verified claim only when the claim itself and an adjacent supporting source marker appear together.
- Source URL normalization accepts only HTTP(S), rejects embedded credentials, and safely preserves IPv6 hosts.
- Quality grades and evidence families stay source-specific; only duplicate normalized URLs are reconciled conservatively, and harmless `www.` host aliases do not create false mismatches.
- Named custom agents use self-contained no-history prompts, inspect active tool schemas, and follow bounded search-tool-call budgets with explicit stop conditions.
- Session initialization exposes a workspace-preserving edit path so macOS `/tmp` projects are not rewritten to an out-of-workspace `/private/tmp` alias.
- Release metadata is generated and checked for both hash mismatches and unlisted distributable files.
- GitHub Actions runs the standard-library test and integrity suite across Python 3.9, 3.11, and 3.14.

### Upgrading existing 3.0 sessions

Existing 3.0 session directories can be retained, but claims with `counter_refuted: true` do not yet have separate `counter_source_urls`. Under 3.1 those claims may become `unresolved` or a process violation until defeating evidence is collected and recorded. Update only the affected entries in `artifacts/agent_returns.json`, then rerun `merge → validate → finalize`. Version 3.1 also strengthens the verification signature, so invalidating and regenerating prior `verification_report.json` and `eval_report.json` is expected.

### Upgrading existing 3.1 sessions

Existing aggregate `artifacts/agent_returns.json` files remain valid. New work should save one completed return per axis under `artifacts/agent_returns/`; when that directory contains JSON files, it takes precedence over the legacy aggregate. Rerun `validate → finalize` after adding canonical Markdown links such as `[src_001](https://example.org/source)` to every cited source.

Claims from existing sessions default to `claim_scope: synthesized`. To use the
source-attributed path, recollect the affected return with an explicit
`claim_scope: attributed`, an `attribution` string that appears in the claim text,
and a directly opened A/B-grade primary source with `access.status: ok`.

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

In a Codex installation with enough skills to trigger a skill-description context-budget warning, explicit `$insane-research` invocation is the reliable entry point.

## Runtime workflow

```text
scope → plan 2–3 standard or 3–4 strict axes → parallel read-only subagents
→ isolated per-axis returns → parent merge
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
