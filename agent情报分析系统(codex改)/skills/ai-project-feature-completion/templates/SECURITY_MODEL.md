# Security and Privacy Model

## Assets and data classes
| Asset/data | Sensitivity | Owner | Storage/location | Retention/deletion | Controls |
|---|---|---|---|---|---|

## Actors, permissions and trust boundaries
- User roles and least-privilege capabilities:
- Tenant/account isolation rules:
- External services and trust assumptions:

## Threat scenarios
| Threat | Entry point | Preconditions | Impact | Preventive control | Detection | Test/evidence | Residual risk |
|---|---|---|---|---|---|---|---|

For AI/Agent systems consider prompt injection, malicious retrieved content, tool overreach, secret exfiltration, cross-user memory leakage, unsafe code execution, excessive autonomy, denial of wallet/resource exhaustion and untrusted output rendering.

## Secrets, dependencies and operations
- Secret source/rotation; never place secrets in source or logs:
- Dependency pinning and vulnerability response:
- Logging redaction and audit trail:
- Rate/time/token/cost limits:
- Incident contact / response path:

## Validation and acceptance
- Negative tests:
- Required scans and actual results:
- Unresolved high-risk items and explicit acceptance owner:
