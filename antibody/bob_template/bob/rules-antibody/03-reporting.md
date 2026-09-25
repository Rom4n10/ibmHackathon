# Reporting (keep it short, it ends up in screenshots)

After each phase, write at most five lines. At the end, print exactly this block:

```
ANTIBODY REPORT
Root cause: <one sentence>
Twins: <confirmed> confirmed, <fixed> fixed, <suspected> suspected, <rejected> rejected
Immunity: <round 0>% -> <final>% after <n> rounds
Antibody: .antibody/antibodies/<NNN-slug>/
Time: <minutes> min (manual baseline: <minutes> min, <twins> twins, if recorded)
```

Take numbers only from CLI output (`antibody status`). Never estimate them.
