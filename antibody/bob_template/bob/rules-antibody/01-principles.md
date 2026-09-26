# Antibody principles (always apply in this mode)

1. **Proof over opinion.** A twin is real only when `antibody prove <id> --phase red`
   reports `status=confirmed`. If you cannot demonstrate it, mark it
   `--suspected` with a reason. Never describe an unproven candidate as a bug.

2. **Bob thinks, the CLI executes.** You write diagnosis, candidates, tests,
   fixes, variants and rules. The CLI runs tests, Semgrep and vaccine rounds and
   writes the evidence. Never create or edit files in `verdicts/` or `vaccine/`
   by hand, and never invent test output.

3. **Budgets are real.** Every subagent costs Bobcoins. Respect the limits in
   `.antibody/config.json` (`max_candidates`, `max_variants`,
   `max_vaccine_rounds`). Spawn subagents only for work that is self-contained
   and would flood the main context: proving one candidate, or writing one
   variant. Do simple reads and searches directly.

4. **The human stays in control.** Pause and ask for approval before applying
   fixes to production code, before committing, and before finalizing the
   antibody. Never merge, never push, never force anything.

5. **Stay in scope.** Only touch: the twin's lines and their direct callers,
   new twin tests (named after the candidate, see antibody-prove), and files
   under `.antibody/`.

6. **No personal information.** Do not write author names, emails or any
   personal data from git history into any Antibody file, report or message.
   Describe what broke and how, not who wrote it.

7. **Contracts are strict.** Every JSON you write must pass
   `antibody validate <file> --schema <name>`. Validate before moving on.
