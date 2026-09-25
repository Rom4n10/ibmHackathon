---
description: Run the full Antibody pipeline on a bug fix
argument-hint: <fix-commit-sha | path/to/postmortem.md>
---

Run the Antibody pipeline from `.bob/rules-antibody/02-pipeline.md` on: $ARGUMENTS

If the argument is a file path, start with `antibody new --document <path>`;
otherwise treat it as a fix commit and start with `antibody new --commit <sha>`.
Respect the budgets in `.antibody/config.json` and pause for approval where the
pipeline says so.
