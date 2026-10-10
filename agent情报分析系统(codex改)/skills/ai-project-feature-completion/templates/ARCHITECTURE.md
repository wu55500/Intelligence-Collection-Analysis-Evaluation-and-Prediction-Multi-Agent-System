# Architecture Record

## Context and system boundary
- User/system actors:
- Trust boundaries:
- In scope / out of scope:

## Diagrams
Add context/container/component and key sequence/data-flow diagrams. Label only components that actually exist or are explicitly proposed.

## End-to-end request/job path
`input → validation → authn/authz → business logic/agent → persistence/dependencies → output/error → telemetry`

Expand for the real stack: client, DNS, IP/port, TLS, CDN/WAF/proxy/gateway where present, API, DB/cache/queue/vector store, model providers, object storage and notifications.

## Component contracts
| Component | Responsibility | Inputs/outputs | State/data owner | Failure behavior | SLO/target | Tests |
|---|---|---|---|---|---|---|

## Data and interfaces
- API schemas/versioning/error semantics:
- Data model and migrations:
- Authentication/authorization:
- Idempotency, timeouts, retries, rate limits:
- Data retention, privacy and lineage:

## Deployment and resource plan
- Environments and topology:
- CPU/RAM/disk/GPU/VRAM/model requirements:
- OS/runtime/native dependencies:
- Network egress, DNS/TLS, API quotas and secrets:
- Estimated cost and assumptions:
- Backup/recovery/rollback:

## Alternatives / ADR links
| Decision | Chosen option | Alternatives | Trade-off | Why fit the requirement | Reconsider if |
|---|---|---|---|---|---|

## Risks and limitations
- Highest-risk failure modes:
- Known gaps:
