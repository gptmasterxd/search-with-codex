# Repository instructions

This repository is a Codex-native derivative of `fivetaku/insane-research`.

## Development constraints

- Preserve the upstream MIT copyright and attribution.
- Keep the skill self-contained under `skills/insane-research/`.
- Treat `skills/insane-research/` as canonical. Never edit `.agents/skills/insane-research/` directly.
- After changing the canonical skill, run `python3 scripts/sync_skill.py` so the repo-local `.agents/skills/` copy stays identical.
- Use only the Python standard library in runtime scripts unless the project explicitly changes that policy.
- Do not add automatic stars, telemetry, network calls, credential access, or destructive installation behavior.
- Deterministic scripts must never fabricate research data. A malformed input should fail with a clear nonzero exit code.
- Parallel research agents return JSON to the parent; they must not concurrently edit shared session files.

## Required checks

```bash
python3 -m compileall -q skills/insane-research/scripts
python3 -m unittest discover -s tests -v
python3 scripts/verify_package.py
python3 scripts/update_release_metadata.py --check
python3 scripts/verify_release.py
```

## Versioning

When behavior changes, update these together:

- `.codex-plugin/plugin.json`
- `skills/insane-research/scripts/researchctl.py`
- `pyproject.toml`
- `MANIFEST.json` (regenerate; do not hand-edit hashes)
- `CHANGELOG.md`
- `README.md` and `README.ko.md` when user-visible

After any distributable-file change, run `python3 scripts/update_release_metadata.py`, review both generated-file diffs, then rerun the required checks.
