---
name: antibody-diagnose
description: Phase 1 of Antibody. Read a bug fix (diff, commit message, linked issue) or a postmortem and extract the abstract root cause as diagnosis.json.
---

# Diagnose the infection

## Inputs to read
1. `git show <fix_sha>`: the diff tells you what was wrong and what "right" looks like.
2. The commit message and the linked issue or PR description, if any.
3. For a postmortem or incident log: the timeline, the root cause section and
   any stack traces. Attached PDF or DOCX files can be read directly.

## What a good root cause looks like
The pattern describes **the mistake**, so it can be found anywhere. It never
names the file, the endpoint or the ticket.

| Bad (a location) | Good (a mistake) |
|---|---|
| "/pay crashed on expired invoices" | "An aware datetime is compared with a naive datetime.now()" |
| "OrdersRepo.save lost updates" | "Read-modify-write on a row without a lock or version check" |
| "Timeout in the Stripe client" | "Outbound HTTP call without a timeout inside a request handler" |

Check yourself: could a teammate find a twin in a file they have never seen,
using only `root_cause.pattern`? If not, rewrite it.

## Output: RUN/diagnosis.json
```json
{
  "run_id": "<run_id>",
  "source": {"type": "fix_commit", "ref": "<sha>", "fix_commit": "<sha>",
             "parent_commit": "<sha^>", "issue": "<url or null>"},
  "root_cause": {
    "title": "One sentence a human can repeat. No file names.",
    "pattern": "The abstract code-level mistake.",
    "why_it_breaks": "The mechanism, in one or two sentences.",
    "trigger_conditions": ["when it actually fails"],
    "fix_strategy": "The general fix, not the diff.",
    "language": "python"
  },
  "original_instance": {"file": "path/before/fix.py", "line": 88, "snippet": "the buggy line"}
}
```
`language` is the project's language as Semgrep names it (`python`, `javascript`,
`typescript`, `java`, `kotlin`, `go`, `csharp`, `ruby`, `php`, `rust`...): the
vaccine rule's `languages:` comes from it.

Copy `source` from `.antibody/runs/<run_id>/run.json`. Then run
`antibody validate RUN/diagnosis.json --schema diagnosis`.

Do not include author names or emails from git history.
