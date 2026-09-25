---
name: antibody-twins
description: Phase 2a of Antibody. Search the entire repository by meaning for other instances of the diagnosed mistake and write a ranked candidates.json.
---

# Hunt for twins

## Search by meaning, in layers
1. **Same API, same misuse.** Every call to the API at the heart of the pattern
   (for example every `now()`, `utcnow()`, `today()`).
2. **Same data, different code.** Every place that handles the same kind of value
   (for example every field loaded from the same column type).
3. **Same shape, different syntax.** Reversed operands, subtraction instead of
   comparison, the value stored in a variable first, a helper that wraps the call.
4. **Same mistake, other modules.** Services, jobs, scripts and tests share habits.

Plain text search is a starting point, never the answer. Read each hit in
context and keep only code where the trigger conditions can actually happen.

## Ranking and budget
- Keep at most `max_candidates` (see `.antibody/config.json`), best first.
- `high`: the trigger conditions clearly hold. `medium`: plausible, needs a test
  to know. `low`: same syntax, but you doubt it can fail.
- Skip the original instance; it is already fixed.

## Output: RUN/candidates.json
```json
{
  "run_id": "<run_id>",
  "search_notes": "What you searched and what you ruled out, in two sentences.",
  "candidates": [
    {"id": "c01", "file": "billing/subscriptions.py", "line": 142,
     "snippet": "if sub.renews_at <= datetime.now():",
     "reasoning": "Why this is the same mistake, in one or two sentences.",
     "confidence": "high"}
  ]
}
```
Ids are `c01`, `c02`, ... Run `antibody validate RUN/candidates.json --schema candidates`.
