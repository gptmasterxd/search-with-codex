# Base Codex comparison benchmark

This harness runs the same research prompts in isolated real Codex CLI projects:

- `with_skill`: installs the current checkout project-locally.
- `without_skill`: uses base Codex without a project-local research skill.

Both arms use Codex's authoritative plugin inventory to disable every enabled
external plugin and every non-system personal/plugin skill. Built-in system
skills remain available, and only the `with_skill` arm gets the current
checkout through project-local installation. Both arms also use
`--ignore-user-config`, `--ignore-rules`, the same model, sandbox, web-search
setting, prompts, and timeouts. The harness does not replace `CODEX_HOME`, so
authentication stays on the user's normal supported path.

Raw transcripts and generated research packages are written outside the
repository. Commit only reviewed aggregate results.

## Run

```bash
WORKSPACE="../insane-research-codex-benchmark-workspace"

python3 benchmarks/benchmark.py run \
  --workspace "$WORKSPACE" \
  --model gpt-5.6-sol

python3 benchmarks/benchmark.py judge \
  --workspace "$WORKSPACE" \
  --model gpt-5.6-sol

python3 benchmarks/benchmark.py report \
  --workspace "$WORKSPACE"
```

`all` runs the three stages in order. Keeping them separate makes interruption,
inspection, and selective re-grading practical.

The runner launches every with-skill and base arm in one bounded worker pool.
Each run stores:

- the final report and copied research audit outputs;
- Codex JSONL events and stderr;
- wall time and token usage from `turn.completed` (`input_tokens +
  output_tokens`; cached and reasoning fields are retained as breakdowns);
- deterministic expectation grades;
- the isolated project used for the run.

The judge randomizes A/B labels per evaluation and emits structured blind
scores for correctness, completeness, evidence quality, uncertainty handling,
and decision usefulness. `report` unblinds only after judging and creates
`benchmark.json` plus `benchmark.md`.

## Review viewer

When the local `skill-creator` skill is available, generate its static review
viewer after `report`:

```bash
python ~/.codex/skills/skill-creator/eval-viewer/generate_review.py \
  "$WORKSPACE/iteration-1" \
  --skill-name "insane-research" \
  --benchmark "$WORKSPACE/iteration-1/benchmark.json" \
  --static "$WORKSPACE/iteration-1/review.html"
```

The deterministic pass rate intentionally scores only output properties shared
by both arms. It evaluates the candidate's `01_full_report.md` and base Codex's
final response; copied state, verification, and evaluation files are excluded
from content scoring and blind judging. Phase-7 verification and final-audit
success are reported as a separate auditability metric so the skill does not
win merely because the baseline lacks its internal file format.
