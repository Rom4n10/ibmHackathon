# Antibody pipeline

Input: a fix commit SHA (default), a PR, or a postmortem/incident document.
Work in the target repository root. `RUN` means the folder printed by
`antibody new` (`.antibody/runs/<run_id>/`).

## Phase 0: start
- `antibody new --commit <sha>` (or `--document <path>` for a postmortem).
- Read the fix diff: `git show <sha>`. Read the linked issue if one exists.

## Phase 1: infection (skill: antibody-diagnose)
- Write `RUN/diagnosis.json`. The pattern must describe the mistake, never a location.
- `antibody validate RUN/diagnosis.json --schema diagnosis`
- Show the one-sentence root cause and wait for a thumbs-up.

## Phase 2: antibodies (skills: antibody-twins, antibody-prove)
- Search the whole repository by meaning, not by text. Write `RUN/candidates.json`
  with at most `max_candidates` entries, best first.
- For each candidate, spawn one subagent (in parallel when possible) that:
  writes `tests/antibody/test_twin_<cid>_<topic>.py`, runs
  `antibody prove <cid> --test <file> --phase red`, and iterates until the
  test fails for the right reason or gives up and runs
  `antibody mark <cid> --suspected --reason "..."`.
- Reject non-twins with `antibody mark <cid> --rejected --reason "..."`.
- Ask for approval, then apply the minimal fix to each confirmed twin and run
  `antibody prove <cid> --test <file> --phase green --fix-summary "..."`.
- Ask the human to commit fixes and tests (the vaccine runs on HEAD).

## Phase 3: vaccine (skill: antibody-vaccine)
Blue team and red team are kept apart so the rule cannot be tailored to the attack.
- **Blue team (you):** write `RUN/rule.v1.yml` from the diagnosis and the proven
  twins only, before any variant exists.
- **Red team (one subagent):** writes `RUN/variants.json` and `RUN/variants/vNN.patch`
  (at most `max_variants`) from `diagnosis.json` only. It must not read any
  `rule.v*.yml` file.
- Round 0, existing defenses only: `antibody vaccine --round 0`
- Round 1: `antibody vaccine --round 1 --rule RUN/rule.v1.yml`
- For each escaped variant, explain in one line why the rule missed it, write
  the next version by generalizing the mistake (never one pattern per escape)
  and run the next round. Stop at 100% or at `max_vaccine_rounds`.

## Phase 4: memory (skill: antibody-memory)
- Make sure the final rule message says what happened last time and points to
  the fix commit or issue.
- Ask for approval, then:
  `antibody finalize --slug <kebab-name> --rule RUN/rule.vN.yml --summary "..." --link <issue-or-pr>`
- `antibody scoreboard --repo-label <owner/project>`
- End with the final summary described in 03-reporting.md.
