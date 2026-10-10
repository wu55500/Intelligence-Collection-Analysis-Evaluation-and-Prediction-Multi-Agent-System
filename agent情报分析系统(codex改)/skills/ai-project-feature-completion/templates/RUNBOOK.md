# Operations Runbook

## Service summary
- Purpose / owner:
- Environment and deployment identifiers:
- Dependencies:
- Normal start/stop/redeploy procedure:

## Observability
- Logs, metrics, traces and correlation/request IDs:
- Key signals / alert thresholds:
- PII/secret redaction:

## Common failure diagnosis
| Symptom | First evidence | Likely layers | Safe checks | Recovery / escalation |
|---|---|---|---|---|

Trace network issues layer by layer: domain/DNS → IP/route → port/firewall/listener → TLS → HTTP/API → app/authz → DB/cache/queue/model provider → client rendering. Do not change unrelated layers without evidence.

## Recovery
- Backup schedule and location:
- Restore procedure and last verified restore:
- Rollback procedure:
- Migration recovery:
- Rate-limit/provider outage fallback:
- Known recovery time/data-loss assumptions:

## On-call/incident record
- Incident severity and owner:
- Timeline/evidence:
- Customer/data impact:
- Mitigation/root cause:
- Follow-up action and verification:
