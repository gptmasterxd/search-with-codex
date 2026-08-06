# Workflow checklist

## Before search

- [ ] Exact question, jurisdiction, date, and audience are recorded.
- [ ] Standard or strict mode is selected.
- [ ] Session is initialized and its absolute path is known.
- [ ] Research plan contains 3–5 independent axes.

## Retrieval

- [ ] Each subagent owns one axis and returns structured JSON only.
- [ ] High-risk claims have counter-searches.
- [ ] Defeated claims identify separate `counter_source_urls`; supporting and counter-evidence are not conflated.
- [ ] Primary-source attempts are documented.
- [ ] Search dates and content validity dates are distinct.
- [ ] Source families identify duplicated underlying evidence.
- [ ] Dead ends and access limits are recorded.

## Merge and verification

- [ ] Parent writes one `agent_returns.json`.
- [ ] `merge` completed and warnings were reviewed.
- [ ] Source registry and claim ledger are readable.
- [ ] `validate` exited 0.
- [ ] Evidence was not edited after validation; if it was, `validate` was rerun.
- [ ] Report body uses verified high-risk claims only.

## Finalization

- [ ] Executive summary and full report exist.
- [ ] Source markers use registered IDs.
- [ ] Each used verified claim has an adjacent supporting source marker.
- [ ] Unresolved and refuted claims have dedicated annexes.
- [ ] `finalize` exited 0 and `eval_report.json` says PASS.
- [ ] Material access limitations are disclosed to the user.
