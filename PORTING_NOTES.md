# Codex porting notes

## 1. Discovery and packaging

The original Claude plugin layout is replaced by both Codex-supported surfaces:

- `skills/insane-research/` for plugin packaging;
- `.agents/skills/insane-research/` for repository-scoped discovery.

`agents/openai.yaml` provides display metadata and enables implicit invocation.

## 2. Subagent model

The original agent/task orchestration is expressed as Codex custom agents in `.codex/agents/*.toml`. Research agents are read-only and return structured JSON. The parent saves each completed result to a distinct `artifacts/agent_returns/*.json` file, so no concurrent operation patches one shared aggregate. The merger still accepts the legacy `artifacts/agent_returns.json` format.

## 3. Search portability

No specific search provider is required. The skill adapts to native web access, browser tools, repository connectors, academic tools, or user-configured MCP servers. When none are available, it must disclose the limitation rather than fabricate current research.

## 4. Deterministic control plane

`researchctl.py` consolidates session and gate operations:

```text
init → merge → validate → synthesize → finalize
```

Runtime uses only the Python standard library.

## 5. Verification hardening

Compared with a prompt-only port, this version adds or makes explicit:

- source-family independence, not only domain counts;
- safe URL normalization and tracking-parameter removal;
- modal per-domain source-grade normalization, with conservative tie-breaking;
- strict mode requiring three independent source families for high-risk claims;
- explicit primary-source and counter-search requirements;
- executable proof with command, output, and verdict;
- signed verification state based on source registry, claim ledger, and verified output;
- final report checks for dangling source IDs, missing user-visible registered URLs, and unresolved/refuted claim leakage.

## 6. Security changes

- Removed automatic setup, starring, and hidden first-run side effects.
- Added a retrieval prompt-injection boundary.
- Kept subagents read-only by default.
- Installation is explicit and local; existing installations are not overwritten without `--force`.
- No credentials, browser sessions, or network services are configured by this package.

## 7. Intentional limits

The verifier establishes that evidence-processing rules were followed; it does not prove that a source is truthful or that an LLM interpreted it correctly. Human review remains necessary for consequential medical, legal, financial, or safety decisions.
