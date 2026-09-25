---
name: antibody-prove
description: Phase 2b of Antibody, designed to run inside one subagent per candidate. Write a minimal test that demonstrates the twin, record red evidence with the CLI, and later verify the fix with green evidence.
---

# Prove one twin

You own exactly one candidate id. Do not touch other candidates' files.

## Write the test
- File: `tests/antibody/test_twin_<cid>_<topic>.py`. One test function.
- Call the real code path through its public function, with the input that
  meets the trigger conditions (for example an aware datetime).
- Deterministic: no network, no sleeps, no real clock dependence beyond the bug
  itself, no external services. Use the smallest fixture that works.
- Assert the correct behavior, so the test fails today and passes after the fix.

## Record red evidence
```
antibody prove <cid> --test tests/antibody/test_twin_<cid>_<topic>.py --phase red
```
- `status=confirmed`: done. Check the output tail fails **for the right reason**
  (the error from `why_it_breaks`, not a typo or a missing fixture).
- Test passes: your input did not meet the trigger conditions, or this is not a
  twin. Adjust once or twice.
- Exit 2 to 5: your test is broken (import, syntax, collection). Fix the test.

Give up after three attempts:
`antibody mark <cid> --suspected --reason "<what blocked the test>"`
If you realize it is not the same mistake:
`antibody mark <cid> --rejected --reason "<why>"`

## Fix and record green evidence (only after human approval)
- Apply the minimal fix that follows `root_cause.fix_strategy`. No refactors.
- `antibody prove <cid> --test <file> --phase green --fix-summary "<one line>"`

## Return to the main agent
One line: `<cid> <status> <file>:<line> <test file>`.
