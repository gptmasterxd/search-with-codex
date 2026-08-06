# Workflow checklist

## Before search

- [ ] Exact question, jurisdiction, date, and audience are recorded.
- [ ] Standard or strict mode is selected.
- [ ] Session is initialized and its absolute path is known.
- [ ] Research plan uses the smallest complete set: 2–3 standard axes or 3–4 strict axes.
- [ ] Current medical, legal, regulatory, standards, or fast-moving technical work includes a 24-month direct-primary freshness sweep.

## Retrieval

- [ ] Each subagent owns one axis and returns structured JSON only.
- [ ] Named custom roles use self-contained prompts without a full-history fork.
- [ ] Active tool schemas were inspected; structured search arguments were not guessed.
- [ ] Per-axis search-tool budgets and the no-new-evidence stop condition are recorded.
- [ ] High-risk claims have counter-searches.
- [ ] Defeated claims identify separate `counter_source_urls`; supporting and counter-evidence are not conflated.
- [ ] Primary-source attempts are documented.
- [ ] Search dates and content validity dates are distinct.
- [ ] Decision-changing recent primary identifiers were opened and checked for exact title, type, date, and result status; blocked PubMed HTML used an official NCBI machine-readable route before closure, and protocol/registry records were reconciled with later publications.
- [ ] Current medical comparisons used a date-bounded PICO/design bibliographic query with full names/acronyms/delivery aliases, preserved recent positive and null direct studies, audited overlapping reviews for contrary syntheses, and used a separate registry/publication linkage route.
- [ ] `search_count` counts tool invocations, while `queries_run` lists the exact literal submitted query strings rather than category labels.
- [ ] Aggregators and mirrors are classified as the inspected artifacts and replaced by canonical records for attributed primary-result claims whenever reachable.
- [ ] Broad technical compatibility claims use a labeled breadth index plus version-specific first-party checks for representative dependencies.
- [ ] Source families identify duplicated underlying evidence.
- [ ] Every claim declares `claim_scope`; attributed text visibly names its authority and synthesized conclusions retain independent evidence.
- [ ] Dead ends and access limits are recorded.
- [ ] Every explicit research question/outcome has usable evidence or a named gap; remaining budget was used only for a missing material item.
- [ ] Intervening legal or technical changes identify the operative provision and effect, not merely a newer document number.

## Merge and verification

- [ ] Parent saves one completed JSON file per axis under `artifacts/agent_returns/`.
- [ ] No two operations patch the same agent-return file.
- [ ] `merge` completed and warnings were reviewed.
- [ ] Source registry and claim ledger are readable.
- [ ] `validate` exited 0.
- [ ] `brief` was read once instead of replaying complete registry and status files.
- [ ] Evidence was not edited after validation; if it was, `validate` was rerun.
- [ ] Report body uses verified high-risk claims only.
- [ ] Attributed claims remain visibly attributed and are not generalized beyond the inspected source.
- [ ] The evidence synthesis contains only a decision-critical subset and does not duplicate the complete internal ledger or repeat the findings as a second claim list.

## Finalization

- [ ] Executive summary and full report exist.
- [ ] Source markers use registered IDs.
- [ ] Every used source marker or descriptive citation label is a Markdown link to its registered canonical URL.
- [ ] Each used verified claim has an adjacent supporting source marker.
- [ ] Unresolved and refuted claims have dedicated annexes.
- [ ] Unresolved/refuted wording and IDs do not appear outside their dedicated annexes.
- [ ] A final editorial pass removed typos, malformed units, duplicated sections, inconsistent terminology, and noncanonical source substitutions without adding facts.
- [ ] No verbatim English claim-coverage or ledger-replay section was added after a natural-language report; attributed paraphrases keep the named authority and canonical link adjacent.
- [ ] `finalize` exited 0 and `eval_report.json` says PASS.
- [ ] Material access limitations are disclosed to the user.
