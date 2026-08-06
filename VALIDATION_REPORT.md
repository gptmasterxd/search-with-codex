# Validation report

**Release candidate:** 3.2.0
**Validated skill source head:** `8a86593acbd0120a3c472a6cd3968219357cb7fc`
**Candidate skill Git tree:** `b5543f0c8a35a4d7689406fa328ee830669dcc52`
**Validated through:** 2026-08-07
**Codex runtime:** Codex CLI 0.146.1 · `gpt-5.6-sol`
**Local Python runtime:** 3.13.5
**Release verdict:** **PENDING** — one final benchmark arm is waiting for the
Codex account usage-limit reset. This is not yet a public-release PASS.

## Deterministic and package checks

- Python compilation: **PASS**
- Python 3.13 unit and integration tests: **PASS** — 69 tests
- Python 3.11 unit and integration tests: **PASS** — 69 tests
- Python 3.14 unit and integration tests: **PASS** — 69 tests
- Package integrity: **PASS** — version 3.2.0, 10 skill files, 5 custom agents
- Release metadata exact-set audit: **PASS** — 62 files
- Release checksum and completeness audit: **PASS** — 62 files
- Canonical skill and repository-local mirror: **PASS**
- Git diff whitespace check: **PASS**

## Real Codex primary-flow verification

These are real `codex --search exec` sessions through the project-local
`$insane-research` entry point. Deterministic tests and copied audit files
support these results but do not replace the model-driven runs.

### Standard mode

The final v3.2 benchmark candidate created one research session and completed
the intended `init → parallel returns → merge → validate → finalize` flow:

- phase 7, status `complete`, mode `standard`
- 11 registered and cited sources
- 11 verified claims, 0 unresolved, 0 refuted
- verification **PASS**
- final report audit **PASS**
- citation resolution 1.0
- visible citation URL coverage 1.0
- orphan source rate 0
- verified claim coverage 1.0
- leak rate 0

### Strict medical mode

The final v3.2 benchmark candidate completed the same primary flow in strict
mode:

- phase 7, status `complete`, mode `strict`
- 15 registered sources and 12 cited sources
- 9 verified claims, 3 explicitly unresolved, 0 refuted
- verification **PASS**
- final report audit **PASS**
- citation resolution 1.0
- visible citation URL coverage 1.0
- orphan source rate 0.2
- verified claim coverage 0.777778
- leak rate 0

A separate focused strict-medical blind comparison on the same final candidate
skill tree scored the skill report **4.7/5** and base Codex **4.3/5**. The judge
preferred the skill report's balanced treatment of conflicting direct and
indirect evidence, named guidelines, limitations, and decision framing.

### Interruption and resume

The live Codex thread `019fd79d-a479-74d2-b510-ec12207caa7f` was interrupted
after one worker completed. Resuming that same thread restored the existing
session, retained the completed return, reran only aborted axes, created no
duplicate research session, and reached phase 7 with a final audit PASS.
Verification signature:
`41f4013721fbd0567876ef93fe839eaa86083777ca57b85621f7567a169bdc5e`.

After runtime fixes, the PR #1 release head was also rechecked through the
project-local entry point: standard, strict medical, and resumed sessions all
reached phase 7 and passed their final audits. Those results are recorded in
the PR #1 verification ledger.

## Final base-Codex benchmark status

The final R11 run uses isolated real Codex CLI projects, the same model and
prompts, no user rules, all non-system skills/plugins disabled in both arms,
and the candidate installed only into `with_skill`.

Five of six model runs completed with return code 0 and deterministic pass rate
1.0:

| Evaluation | Candidate | Base Codex |
|---|---:|---:|
| Python free-threading · standard | PASS | PASS |
| TKA analgesia · strict medical | PASS | PASS |
| EU AI Act open-source · strict legal | `usage_limit` before model execution | PASS |

The interrupted legal candidate consumed zero tokens. Codex reported the
account reset time as **2026-08-08 12:51 PM**. The benchmark's actual
`--resume` path then:

- retained all five successful reports, timings, and token records;
- reran only the interrupted legal candidate arm;
- archived the first failure as `attempt-1`;
- captured the top-level JSONL failure;
- classified the result as the infrastructure status `usage_limit`.

The comparison remains invalid until that arm completes and all three blind
judgments are read back. No incomplete score is presented as a product result.

## Remaining release gates

- Resume the one infrastructure-interrupted legal candidate arm.
- Run all three blind judgments and aggregate the exact candidate results.
- Replace this pending verdict with the final benchmark readback.
- Merge PR #2, tag v3.2.0, make the repository public, and enable main
  protection.
- Create the public release and verify a fresh public clone, project-local
  install, doctor check, and release integrity through the supported entry
  point.
