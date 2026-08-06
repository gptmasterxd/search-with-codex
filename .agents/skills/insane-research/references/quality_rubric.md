# Source quality rubric

Grades measure evidentiary fitness for the specific claim, not prestige alone.

Also distinguish evidence form. A directly inspected authoritative source can verify an
`attributed` statement about what that source says, but it does not by itself verify a
`synthesized` real-world effect or interpretation. For example, one RCT can verify “the
trial reported X”; a broader clinical-effect claim still needs independent synthesis.

## A — strongest primary evidence

- peer-reviewed systematic review or high-quality primary study appropriate to the question;
- enacted law, official regulation, court opinion, regulator database, audited filing, official statistics;
- normative specification or versioned first-party technical documentation;
- reproducible primary dataset or repository evidence with an exact version.

## B — strong authoritative evidence

- official guidance, institutional report, high-quality professional guideline;
- well-documented first-party release notes or technical documentation;
- reputable research institute or industry report with transparent methodology;
- high-quality peer-reviewed study with material limitations for this exact claim.

## C — useful expert or journalistic evidence

- reputable reporting with named sources and independent verification;
- expert analysis with disclosed method and citations;
- conference material or secondary technical analysis that can support context but is not the authoritative origin.

## D — provisional or interested evidence

- preprint not yet peer-reviewed;
- vendor whitepaper, company blog, marketing survey, advocacy material;
- weakly documented aggregator or secondary summary.

## E — lead only

- anonymous forum, social-media post, unsourced list, anecdote, generated summary, or speculation.

## Source-specific consistency

Grade the exact document for the exact claim. A domain can host a systematic review, an editorial, and a press release with legitimately different evidentiary grades. Do not normalize all documents on one hostname to one grade.

When multiple agents return the same normalized URL with different grades, the merger selects the modal grade and the more conservative grade on ties. This reconciles contradictory assessments of one source without flattening unrelated documents from the same host.

## Claim-specific cautions

- A source may be high quality but irrelevant to the exact population, jurisdiction, version, or date.
- A corporate filing is primary for what the company reported, not necessarily proof of an external causal claim.
- A review article may be secondary even when published in a prestigious journal.
- A news article does not become an independent source when it merely repeats an official announcement.
- A search snippet cannot receive direct-inspection credit. When title, publication type,
  version, result status, article section, or table context matters, open the canonical
  record and record `access.status: ok` only after checking it.
