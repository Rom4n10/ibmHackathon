# AGENTS.md: context for Bob while building Antibody

This file is for Bob sessions that **build Antibody itself**. The mode that
Antibody installs in other repositories lives in `antibody/bob_template/bob/`.

## What this project is
Antibody turns a bug fix into proven twins, fixes and a self-tested Semgrep
rule. Bob does the reasoning (in the Antibody custom mode); the Python CLI in
`antibody/` runs tests, Semgrep and vaccine rounds and records evidence.

## Golden rules
1. **Contracts first.** Every JSON file has a schema in `antibody/schemas/`.
   If you change a schema, update `examples/sample-run/` and the tests in the
   same change. `python -m unittest discover -s tests` must stay green.
2. **Standard library only** in `antibody/`. No runtime dependencies.
   pytest and semgrep are external tools the CLI calls, not imports.
3. **Evidence is written only by the CLI.** Never add code paths that let a
   model write `verdicts/` or `vaccine/` files directly.
4. **Never touch the developer's checkout** during a vaccine round: all
   variant patches are applied in a temporary git worktree.
5. **No personal data.** Nothing in Antibody may store author names or emails
   from git history.
6. Python 3.10+, type hints, small functions, messages Bob can act on
   (say what failed and what to do next).

## File ownership (to avoid merge conflicts while working in parallel)
| Area | Owner | Paths |
|---|---|---|
| Bob mode, rules, skills, command | Workstream A | `antibody/bob_template/**` |
| CLI, schemas, tests | Workstream B | `antibody/*.py`, `antibody/schemas/**`, `tests/**` |
| Scoreboard, demo, pitch, evidence | Workstream C | `ui/**`, `docs/team/**`, `bob_sessions/**`, `DATA_SOURCES.md` |
| Contract examples | A + B together | `examples/sample-run/**` |

## Commands
```bash
python -m unittest discover -s tests      # must pass before every merge
python -m antibody --help                  # CLI without installing
pip install -e ".[tools]"                  # install with pytest and semgrep
```

## Bob usage in this hackathon
- Every task you run counts toward our evidence: keep each task focused on one
  goal and name it clearly, because its summary screenshot goes to `bob_sessions/`.
- Bobcoins are limited (40 per participant, no top-ups). Prefer Plan mode for
  design, Agent mode for implementation, and start a new context window when a
  task changes topic.
