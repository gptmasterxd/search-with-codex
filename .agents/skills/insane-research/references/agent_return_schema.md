# Subagent return contract

Return one JSON object and no surrounding prose. The parent Codex saves each completed object to a separate file under `artifacts/agent_returns/`; do not write or patch session files yourself.

Use the canonical field names exactly. In particular, do not rename `quality_rating` to `quality`, `text` to `claim`, flatten `access`, or return `expand_leads` as strings. Before returning, self-check the top-level, source, claim, and expansion-lead keys against the example below.

```json
{
  "axis": "official-current-state",
  "summary": "Optional concise synthesis of this axis",
  "sources": [
    {
      "url": "https://example.org/document",
      "title": "Document title",
      "domain": "example.org",
      "source_family": "example.org",
      "publisher": "Publisher or issuing body",
      "author": "Author when available",
      "source_type": "official",
      "quality_rating": "A",
      "primary": true,
      "published_at": "2026-07-01",
      "valid_at": "2026-07-01",
      "observed_at": "2026-08-06T12:00:00Z",
      "notes": "What it supports, relevant pages or sections, and limitations",
      "access": {
        "method": "browser|web-search|mcp|local-file|repository|api",
        "status": "ok|partial|blocked"
      }
    }
  ],
  "claims": [
    {
      "text": "One atomic factual claim",
      "risk": "high",
      "claim_type": "numeric",
      "source_urls": [
        "https://example.org/document",
        "https://independent.example.net/data"
      ],
      "counter_source_urls": [],
      "counter_search": "Describe the counter-query and what was or was not found",
      "counter_refuted": false,
      "conflicting": false,
      "primary_source": true,
      "valid_at": "2026-07-01"
    }
  ],
  "queries_run": [
    "exact query actually run"
  ],
  "search_count": 1,
  "expand_leads": [
    {
      "lead": "A material uninvestigated lead",
      "why": "Why it could alter the conclusion",
      "angle": "A concrete next search or source route"
    }
  ],
  "dead_ends": [
    "A route checked that produced no usable independent evidence"
  ]
}
```

## Claim rules

- Keep each claim atomic. Split a sentence containing two independently falsifiable statements.
- `claim_type` must be exactly one of `numeric`, `legal`, `causal`, `financial`, `descriptive`, or `executable`.
- Use `risk: high` for numbers, dates, current status, law, regulation, finance, medicine, safety, causal language, material identity, or deadlines.
- Keep evidence supporting the claim in `source_urls`.
- Put sources that directly contradict and defeat the claim in `counter_source_urls`. Do not place the same source in both lists.
- Use `counter_refuted: true` only when credible contrary evidence defeats the claim and `counter_source_urls` identifies that evidence. Standard mode requires A/B/C counter-evidence; strict high-risk mode requires A/B counter-evidence.
- Use `conflicting: true` when credible sources disagree and the conflict remains unresolved.
- `primary_source: true` means at least one linked source is the authoritative origin for that claim.
- For an executable claim, add:

```json
"execution_proof": {
  "script": "Exact command or minimal reproduction",
  "output": "Relevant output only",
  "env": "OS, runtime, package and tool versions",
  "verdict": "confirmed"
}
```

## Source-family rules

Different domains are not always independent. Use a shared `source_family` when sources repeat the same underlying evidence, including:

- syndication of one wire story;
- several pages from one regulator or corporate group;
- articles based entirely on one press release;
- dashboards and summaries derived from the same dataset;
- mirrors of one repository or document.

The inverse is also possible: separate documents on one hosting domain can belong to different evidence families, such as unrelated journal articles or independently authored repository artifacts. Assign `source_family` from the underlying evidence lineage, not from the hostname alone. Quality grades are also source- and claim-specific. Two documents on one domain may legitimately have different grades. When agents return the same normalized URL more than once, the merger reconciles only that identical source conservatively.

## Search accounting

- `search_count` is the number of actual search or discovery tool invocations.
- One batched call containing several query objects counts as one call.
- Search hits, snippets, opened pages, document reads, and downloads do not increment `search_count`.
- `queries_run` contains every query string submitted, including strings grouped into a batch.
- Normally return at most eight distinct decision-relevant sources and six material claims for one axis. Exceed this only when the parent names a strict-mode evidence gap that cannot otherwise be represented.

## Deterministic compatibility normalization

The merger can preserve an otherwise valid completed return when a model emits one of these observed legacy aliases:

- `quality` → `quality_rating`
- `accessed_at` → `observed_at`
- `key_points` → `notes` when `notes` is absent
- `access_method` / `access_status` → `access.method` / `access.status`
- `claim` → `text`
- boolean `causal` → `claim_type`
- a non-empty string in `expand_leads` → an object with that string as `lead`

These transformations are recorded in `artifacts/merge_report.json` under `normalizations`. They do not invent missing evidence, rationale, URLs, or claim support. Unsupported or lossy shapes remain warnings and must be corrected.
