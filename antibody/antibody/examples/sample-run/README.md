# Sample run (example data)

This folder is a complete, hand-written example of one Antibody run on a
fictional `billing-service`. It is **example data**, not the output of a
real run. It exists so every workstream can build against the same contracts
from hour one:

- Bob's skills must produce files shaped like `diagnosis.json`,
  `candidates.json` and `variants.json`.
- The CLI produces files shaped like `verdicts/`, `vaccine/` and
  `scoreboard.json`.
- `ui/scoreboard.html` renders `scoreboard.json`.

`tests/test_pipeline.py` validates every file here against `antibody/schemas/`,
so if a contract changes, this example must change with it.
