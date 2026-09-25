---
name: antibody-memory
description: Phase 4 of Antibody. Write the rule message that tells future developers what happened last time, then finalize the permanent antibody and the scoreboard.
---

# Remember why

## The rule message is the memory
When this rule blocks someone months from now, the message is all they read.
It must answer three questions in three short sentences:
1. What is wrong with this code?
2. What happened last time? (the incident, with the fix commit or issue id)
3. What to write instead?

Template:
```
<The mistake in plain words>. This exact mistake broke <what users saw>
(fixed in <short sha>, <issue id>) and had <n> hidden twins.
Use <the correct form>. History: .antibody/antibodies/<NNN-slug>/history.md
```
No author names, no emails, no blame.

## Finalize (after human approval)
```
antibody finalize --slug <kebab-case-mistake-name> --rule RUN/rule.vN.yml \
  --summary "<one sentence for future developers>" --link <issue-or-pr-url>
antibody scoreboard --repo-label <owner/project>
antibody status
```
The slug names the mistake (`naive-vs-aware-datetime`), never the file.

Then print the ANTIBODY REPORT block from `.bob/rules-antibody/03-reporting.md`,
using numbers from `antibody status` only.
