---
name: antibody-prove
description: Phase 2b of Antibody, designed to run inside one subagent per candidate. Write a minimal test that demonstrates the twin, record red evidence with the CLI, and later verify the fix with green evidence.
---

# Prove one twin

You own exactly one candidate id. Do not touch other candidates' files.

## Write the test
Use the project's own language, test framework and conventions, so its runner
finds the test. `antibody profiles` shows which runner is configured. One test,
in a new file named after the candidate:

| Profile | Test file (example) |
|---|---|
| python-pytest | `tests/antibody/test_twin_<cid>_<topic>.py` |
| js-vitest, js-jest | `tests/antibody/twin_<cid>_<topic>.test.ts` (or `.js`), where the runner looks |
| java-maven, java-gradle | `src/test/java/<package>/antibody/TwinC01<Topic>Test.java` (class name = file name) |
| go-gotestsum | `<package dir>/antibody_twin_<cid>_test.go`, in the package under test |
| dotnet | `<TestProject>/Antibody/TwinC01<Topic>Tests.cs` |
| others | the framework's usual test folder and naming |

- Call the real code path through its public function, with the input that
  meets the trigger conditions (for example an aware datetime).
- Deterministic: no network, no sleeps, no real clock dependence beyond the bug
  itself, no external services. Use the smallest fixture that works.
- Assert the correct behavior, so the test fails today and passes after the fix.

## Record red evidence
```
antibody prove <cid> --test <test file> --phase red [--node "<test name>"]
```
The CLI runs the file with the project's runner and reads its JUnit report.
Pass `--node` when the file has more than one test.
- `status=confirmed`: the test ran and failed. Check the output tail fails
  **for the right reason** (the error from `why_it_breaks`, not a typo or a
  missing fixture).
- `Test passes`: your input did not meet the trigger conditions, or this is not
  a twin. Adjust once or twice.
- `Test is broken`: it never really ran (compile, import or syntax error, a
  missing runner, or a test name the report does not contain). Fix the test.

Give up after three attempts:
`antibody mark <cid> --suspected --reason "<what blocked the test>"`
If you realize it is not the same mistake:
`antibody mark <cid> --rejected --reason "<why>"`

## Fix and record green evidence (only after human approval)
- Apply the minimal fix that follows `root_cause.fix_strategy`. No refactors.
- `antibody prove <cid> --test <file> --phase green --fix-summary "<one line>"`

## Return to the main agent
One line: `<cid> <status> <file>:<line> <test file>`.
