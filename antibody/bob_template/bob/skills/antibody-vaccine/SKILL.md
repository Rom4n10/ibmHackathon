---
name: antibody-vaccine
description: Phase 3 of Antibody. Write realistic variants of the bug as patches, measure existing defenses, then write and harden a Semgrep rule round by round until it catches every variant.
---

# Vaccinate: attack your own defenses

## Two teams, kept apart
- **Blue team** (main agent) writes `rule.v1.yml` first, from `diagnosis.json`
  and the proven twins. It never sees the variants before round 1.
- **Red team** (one subagent) writes the variants from `diagnosis.json` only.
  It must not open any `rule.v*.yml`. Its goal is to get past a defense it
  cannot see, using mistakes a real teammate could make.
This separation is what makes the Immunity Score meaningful: a rule written
while looking at the attacks would pass by construction.

## Write variants (red team, at most `max_variants`)
Each variant re-introduces the **same mistake** in a shape a teammate could
plausibly write. Aim for one of each kind:

| kind | Example |
|---|---|
| `syntax` | reversed operands, subtraction instead of comparison |
| `relocation` | the original mistake in another module |
| `indirection` | the value stored in a variable or returned by a helper first |
| `api_alias` | an equivalent API with the same flaw (`utcnow()` vs `now()`) |

Rules: one mistake per variant, it must not break imports or syntax, and it
must be realistic, never a contrived puzzle.

## Create each patch
1. Edit the target file in place to introduce the variant.
2. `git diff -- <target_file> > RUN/variants/vNN.patch`
3. `git checkout -- <target_file>` to restore it.
4. Add the entry to `RUN/variants.json`
   (`id`, `kind`, `description`, `target_file`, `patch: "variants/vNN.patch"`).
5. `antibody validate RUN/variants.json --schema variants`

For a variant in a new file, create it, `git add -N <file>`, diff, then delete
the file and `git reset <file>`.

## Rounds
- Round 0, existing defenses only: `antibody vaccine --round 0`
- Round 1 with the blue team's first rule:
  `antibody vaccine --round 1 --rule RUN/rule.v1.yml`
- For every escaped variant, state in one line why the rule missed it, write
  `rule.v2.yml` by generalizing the mistake and run round 2. Stop at 100% or
  `max_vaccine_rounds`. If v1 already reaches 100%, say so: that is a result,
  not a problem to fix.

## Writing the rule
- `languages:` is `root_cause.language` (plus `typescript` next to `javascript`
  when the project mixes both).
- Match the mistake, not the variant: generalize from the escapes
  (`pattern-either`, metavariables) instead of adding one pattern per escape.
- Check it does not over-match: `semgrep scan --config RUN/rule.vN.yml --metrics=off`
  on the clean tree should only report suspected or unfixed places. List any
  surprise and narrow the rule if needed.
- The `message` is the memory (see antibody-memory). Write it well from v1.
