# AI-Assisted Development and Review Log

Record only calls/actions that actually happened. Do not fabricate model names, versions, API integrations, consensus or review results.

| Iteration | Goal / changed paths | Research source/model/tool (if actually used) | Implementer and version | Reviewer and version (independent?) | Findings with evidence | Decision | Tests rerun / results | Commit/artifact |
|---|---|---|---|---|---|---|---|---|

## Synthesis rules
- Separate observation, inference, assumption and recommendation.
- Merge duplicate findings; preserve contradictory findings until resolved.
- A finding requires path/location, impact, failure mechanism and reproduction/verification where feasible.
- Record false positives and why they were rejected.
- Stop when acceptance and mandatory gates pass or state `BLOCKED`; do not create endless subjective polish loops.
- Note AI-generated/third-party code where material and verify license, security, understanding and maintainability.
