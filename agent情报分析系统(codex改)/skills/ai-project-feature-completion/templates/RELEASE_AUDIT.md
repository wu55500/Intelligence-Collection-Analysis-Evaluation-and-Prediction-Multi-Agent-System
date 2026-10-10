# Release Audit

## Release candidate
- Version/commit/tag:
- Environment:
- Project tier:
- Change scope and linked requirements:

## Mandatory gates
| Gate | PASS / FAIL / NOT RUN | Evidence | Owner / resolution |
|---|---|---|---|
| No secret/PII exposure | | | |
| Authorization/tenant isolation | | | |
| Data migration/recovery approved | | | |
| Acceptance-critical tests accurate | | | |
| Only approved scope changed | | | |
| Reproducible install/run path | | | |
| Security/dependency checks appropriate to risk | | | |
| Required human approval present | | | |

## Build/test/deploy evidence
| Check | Command or CI run | Environment | Result | Artifact | Gap |
|---|---|---|---|---|---|

## Rollout / rollback / monitoring
- Pre-deploy backup/migration plan:
- Rollout method:
- Smoke test and expected signal:
- Rollback trigger and action:
- Owner and monitoring period:

## Decision
- `RELEASE READY` / `NOT RELEASE READY` / `PARTIAL` / `BLOCKED`:
- Blocking findings:
- Accepted residual risks, owner and expiry/review date:
