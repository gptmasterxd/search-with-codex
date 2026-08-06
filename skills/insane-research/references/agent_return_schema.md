# Subagent return contract

Return one JSON object and no surrounding prose. The parent Codex will combine several objects and write `artifacts/agent_returns.json`.

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
- Use `risk: high` for numbers, dates, current status, law, regulation, finance, medicine, safety, causal language, material identity, or deadlines.
- Use `counter_refuted: true` only when credible contrary evidence defeats the claim.
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
