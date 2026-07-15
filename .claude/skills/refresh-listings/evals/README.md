# Evals for `refresh-listings`

`evals.json` follows the [agentskills.io skill-eval format](https://agentskills.io/skill-creation/evaluating-skills):
hand-authored test cases (`prompt` + `expected_output` + `assertions`), graded manually or via a subagent — there's
no first-party Claude Code runner for standalone skills, only for skills managed through the `skill-creator` plugin.

## Why these can't run against this checkout directly

The skill's whole job is to `git commit` + `git push origin main`, which would spam the real repo and trigger a real
Vercel deploy for every eval run. Every scenario must run in an isolated sandbox with a fake `origin`.

`uv run python build.py` also makes real (read-only) network calls to ArcGIS and the listing sites for thumbnails —
that's fine to leave live (same calls the app makes normally, and CLAUDE.md's HTTP-mocking rule is specifically about
the pytest *unit* suite, not these integration-style evals), but it does mean thumbnail counts are not fully
deterministic run to run. Assertions are written to tolerate that (e.g. regex on the message shape, not exact counts,
except where a fixture is specifically designed to force `0/N`).

## Running a scenario

```bash
# 1. Fresh sandbox clone, isolated from the real remote
tmp=$(mktemp -d)
git clone --local --no-hardlinks . "$tmp/repo"
cd "$tmp/repo"

# 2. Fake origin so a push can't reach the real GitHub repo
git init --bare "$tmp/fake-origin.git"
git remote set-url origin "$tmp/fake-origin.git"

# 3. Apply the scenario's `setup` step, e.g. for eval id 1:
cp <path-to-checkout>/.claude/skills/refresh-listings/evals/fixtures/two_listings.csv data/housing_data.csv

# 4. Run the scenario's `prompt` against Claude Code with this skill available,
#    with cwd = $tmp/repo, and watch/record what it does
claude -p "I've uploaded a new data file. Kindly refresh data, regenerate map, push changes and redeploy app."

# 5. Grade: check `git log`, `git status`, `git show --stat`, and the assistant's
#    reply text against the scenario's `assertions` in evals.json. Record results
#    (pass/fail per assertion + notes) whichever way you like — e.g. a grading.json
#    alongside this file — before moving to the next scenario.

# 6. Clean up
cd - >/dev/null
rm -rf "$tmp"
```

Repeat per scenario in `evals.json`. Scenario 4 needs an extra `git commit --allow-empty -m tmp` style tweak to
`config.py` (or similar) applied in step 3 alongside the CSV swap — see its `setup` field.

## Adding scenarios

Keep new cases focused on the *judgment calls* the skill has to make (detect no-op, refuse to commit on build failure,
flag anomalies, avoid sweeping in unrelated changes) rather than re-testing `build.py` itself — that belongs in
`tests/test_map.py` / `tests/test_fetchers.py` as a normal pytest case.
