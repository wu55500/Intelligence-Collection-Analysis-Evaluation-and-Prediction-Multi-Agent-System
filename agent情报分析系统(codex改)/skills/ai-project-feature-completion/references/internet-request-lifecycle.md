# Internet and Web Request Lifecycle: Engineering Checklist

This reference turns the “what happens after entering a URL?” mental model into architecture, test, monitoring and troubleshooting questions. Use only layers present in the project; do not add infrastructure just to make the diagram look enterprise-like.

## Logical path

```text
User action
  ↓
Browser/app route and URL parsing
  ↓
DNS/cache resolution → IP address
  ↓
Network path and destination port
  ↓
Transport connection (commonly TCP; QUIC may apply) and TLS for HTTPS
  ↓
HTTP request: method, path, headers, auth/session, body
  ↓
Optional edge: CDN / WAF / load balancer / reverse proxy / API gateway
  ↓
Application router → input validation → authentication → authorization
  ↓
Business logic → optional cache / database / queue / object store / external API / LLM
  ↓
HTTP response: status, headers, body, cache policy, error shape
  ↓
Browser/app handling, rendering, state update and telemetry
```

## Questions to answer in an architecture review

- What exact host, route, method and port does the client use in each environment?
- Which DNS record/resolver and TLS termination path are in use? Which pieces are managed externally?
- Which component accepts public traffic, and which services must remain private?
- Where do authentication and authorization run? Is object-level and tenant-level access checked on the server for every relevant request?
- What is the stable API contract: schema, status codes, error structure, pagination, idempotency and version policy?
- How are timeouts and retries bounded? Can a retry duplicate a payment, job, write or external action?
- Which data is cached, where, for how long, and how is invalidation handled?
- What happens when DB/cache/queue/LLM/external API is slow or unavailable?
- How is a request correlated across frontend, proxy, app and dependencies without logging secrets?
- Does the runbook identify the first checks for DNS, TLS, network/port, proxy, CORS, auth, application, dependency and rendering failures?

## Failure localization matrix

| Symptom | First evidence to collect | Common layers to examine |
|---|---|---|
| Domain cannot resolve | resolver output, DNS records, TTL, environment | domain/DNS/resolver/cache |
| Connection refused | target IP/port, listener status, connection result | address, route, port, firewall/security group, process |
| Connection times out | connect timing, route, edge and server logs | networking, overloaded server, blocked traffic, exhausted pool |
| TLS/certificate error | hostname, validity, chain, negotiated protocol, termination location | certificates, clock, proxy/CDN, TLS config |
| 401/403 | request identity, token/cookie metadata (never raw secrets), server policy log | session/authentication/authorization/CSRF/tenant policy |
| 404/405/422 | route, method, schema and response body | frontend route, API contract, validation, proxy rewrite |
| CORS/browser-only error | preflight `OPTIONS`, response headers, browser console | origin policy, credentials, proxy and browser rules |
| 429/5xx | request ID, rate-limit counters, exception and dependency timing | rate limiting, application, DB, queue, external provider |
| Slow result | DNS/connect/TLS/TTFB/download and dependency spans | edge cache, app CPU, DB query, pool, external API, rendering |
| API correct but UI wrong | raw response, content type, cache state, frontend state | serialization, cache, CORS, parser, state/rendering |

## Minimum verification for a public Web/API project

- A clean environment can run the documented setup.
- Health/readiness endpoints (if used) distinguish process liveness from dependency readiness.
- Input size, request rate, execution time and pagination are bounded.
- All protected operations enforce server-side identity and authorization.
- API errors are predictable and do not expose stack traces/secrets.
- TLS and public/private network boundaries are documented for deployed environments.
- Request/correlation IDs connect edge logs to app/dependency telemetry where available.
- Critical browser flows have automated or recorded end-to-end verification.
- The runbook distinguishes DNS, transport, TLS, HTTP, app, dependency and UI failure layers.

## Important caution

A simplified teaching flow (domain → DNS/IP → port → request/response → browser rendering) is a learning model, not a universal exact packet trace. Browsers, DNS caches, proxies, CDN, HTTP versions and hosting topology can change the concrete sequence. Diagnose the actual deployed path rather than assuming every request follows every box.
