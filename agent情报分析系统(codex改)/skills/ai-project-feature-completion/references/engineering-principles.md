# Engineering Principles and Audit Checklist

## 1. Coding and maintenance
- Follow the repository's language idioms and formatter/linter; pin supported runtime versions.
- Prefer clear names, cohesive modules, explicit interfaces, typed boundaries where practical and errors with actionable context.
- Avoid catch-all exception swallowing, hidden global state, unbounded loops, unvalidated inputs, duplicated business rules and unnecessary abstraction.
- Comment why a non-obvious decision exists, not what each obvious line does.
- Keep secrets/configuration out of source; sanitize logs; document environment variables.
- Update lockfiles and compatibility documentation when dependencies change.
- A reviewer must be able to trace the source of truth for key business rules and identify test coverage.

## 2. Network and system behavior
- Trace actual requests end to end and distinguish DNS, connection, TLS, HTTP, application, dependency and client-rendering failures.
- Define timeout budgets across nested calls; do not retry non-idempotent operations blindly.
- Use idempotency keys or deduplication for retried writes/jobs where required.
- Apply pagination, payload bounds, connection-pool limits, rate limits and cancellation where relevant.
- Make external dependency failure explicit and bounded; design fallback/degraded mode only when product requirements justify it.

## 3. Database and data engineering
- Define ownership, schema constraints, indexes, transaction boundaries, consistency expectations and retention.
- Review migrations for lock time, backfill strategy, backward compatibility, rollback/forward-fix and backup requirements.
- Track provenance, validation, lineage and quality checks in data/ML pipelines.
- Do not put private or regulated production data into unapproved AI services or test fixtures.

## 4. Testing and CI/CD
- Test behavior and invariants rather than only line coverage.
- Include negative/permission/error cases; integration and contract tests for important boundaries; E2E for critical user flows.
- CI should be deterministic, fast enough to run often, and fail on required quality gates.
- Keep test flakiness visible. Do not silence failures merely to make CI green.
- Build/deploy artifacts should identify the version/commit; secrets should be injected via approved mechanisms.
- Use progressive rollout, smoke checks and rollback/forward-fix plans appropriate to the risk.

## 5. Security and AI/Agent-specific controls
- Enforce permissions in code/tool/API boundaries, not solely in prompts.
- Treat retrieved content, webpages, files, tool output and model responses as untrusted.
- Separate planning from privileged execution; require approval for destructive, costly, external or irreversible actions.
- Limit tool permissions, command scope, tokens, calls, runtime, concurrency and spend.
- Validate tool arguments and output schemas; avoid executing generated code without a sandbox appropriate to risk.
- Prevent secrets from entering prompts, embeddings, logs or shared memory; isolate user/tenant memory.
- Add evaluations for prompt injection, refusal/abstention, hallucination, data leakage and unsafe actions when relevant.

## 6. Resource and environment awareness
- Estimate CPU, RAM, disk, GPU/VRAM, model loading, concurrency and bandwidth before selection.
- Record OS/runtime/native dependencies and test the documented environment from a clean state.
- Use containers when they reduce deployment variance, but do not add Docker/Kubernetes automatically if the project and host do not justify them.
- Account for API availability, quota, latency, cost and fallback for hosted model/data services.
- Distinguish local mock success from networked integration and real deployment.

## 7. Observability and resilience
- Use structured logs, correlation IDs and appropriately bounded metrics/traces without exposing sensitive data.
- Define a small set of user-relevant SLIs/targets where appropriate; choose alerts that require action.
- Document health/readiness checks, dependencies, common failures and safe recovery.
- Test backups by restoring them; a backup process without restore evidence is incomplete.
- Document incidents and follow-up actions; do not claim an SLA without operating evidence.

## 8. Review hygiene
- Review the actual diff, dependency changes, migrations and test outputs.
- Prefer the smallest change that satisfies acceptance; identify scope creep explicitly.
- Separate blocking defects from suggestions and cosmetic preferences.
- Every accepted risk has an owner, rationale and revisit trigger.
- Final report distinguishes verified fact, inference, assumption and unknown.
