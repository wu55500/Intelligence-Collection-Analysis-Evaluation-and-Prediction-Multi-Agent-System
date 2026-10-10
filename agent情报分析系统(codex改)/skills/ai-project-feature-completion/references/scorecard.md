# Evidence-Based Project Review Scorecard

Use this rubric as an evidence-backed diagnostic, not a scientific measurement or hiring guarantee. Score only what the reviewer can inspect. Every scored claim must cite a repository path, test output, CI run, deployment result, reproducible demo or written decision. Missing evidence is not a pass.

## Hard gates (outside the points)

Any unresolved item below means `NOT RELEASE-READY` regardless of total score:

- secret or sensitive-data exposure;
- critical access-control/tenant-isolation flaw;
- destructive data migration/action without approved recovery or rollback;
- acceptance-critical failure hidden, misreported, or checks bypassed;
- unauthorized unrelated change or destructive repository operation;
- claimed deliverable has no reproducible run/use path;
- resume claims or performance metrics are unsupported;
- required human approval absent for a high-impact operation.

## General engineering / recruiter rubric (100 points)

| Dimension | Weight | What earns points | Evidence examples |
|---|---:|---|---|
| Problem, requirements and acceptance | 10 | Clear target user/problem, scope, non-goals and testable requirements | Project brief, requirements-to-tests mapping |
| Architecture and request/data flow | 15 | Appropriate module boundaries, APIs/data model, trade-offs and understandable end-to-end flow | Architecture diagram, ADRs, API schema, request trace |
| Code standards and maintainability | 15 | Readable structure, idiomatic syntax, naming/types, error handling, low accidental complexity, useful comments and manageable dependencies | Diff review, lint/type checks, design explanation |
| Tests and correctness | 15 | Relevant unit/integration/contract/E2E/negative/regression tests, clear gaps, repeatable results | Test reports, reproduction steps, failure-case tests |
| Security and privacy | 10 | Authn/authz, data boundaries, input validation, secrets/dependencies, least privilege and AI/tool safety as applicable | Threat model, security tests/scans, permission checks |
| CI/CD and reproducible delivery | 10 | Automated quality gates, pinned dependencies, clean setup, build/release evidence and migration safety | CI workflow history, lockfile, build/deploy logs |
| Reliability, network and operations | 10 | Timeouts, retries/idempotency, observability, resource bounds, runbook, backup/restore appropriate to tier | Logs/metrics/traces, smoke test, recovery evidence |
| Data/AI correctness (if applicable) | 10 | Data lineage/quality, baselines, evaluation set, error analysis, groundedness/abstention and model/cost/version tracking | Evaluation report, dataset notes, experiment logs |
| Documentation and portfolio proof | 5 | Useful README, reproducible demo, credible contribution statement and evidence-backed result | Clean-clone guide, demo, resume evidence ledger |

If data/AI correctness is genuinely not applicable, mark `N/A` with a reason and reallocate those points to relevant dimensions before scoring. Never use `N/A` to evade a difficult requirement.

## Approximate interpretation for interview practice

- **Below 60:** below the conventional pass floor for this practice rubric; identify foundation-level gaps. This is not a universal company cutoff.
- **60–69:** reaches a basic pass floor only if hard gates are clear; still likely to need substantial evidence or maintainability work.
- **70–79:** credible project, with visible limitations; avoid unqualified enterprise claims.
- **80–89:** strong evidence for the declared project tier, with explainable trade-offs and repeatable validation.
- **90–100:** exceptional evidence for scope and tier; independent review is still needed.

The 60-point threshold is a requested practice convention for interview preparation, not a validated hiring predictor. Hard-gate failures override it. A reviewer must give specific reasons and prioritized remediation, not just a number.

## Role-specific weight adjustment

Use the general rubric as the default, then reweight before reviewing—not after seeing the results—to match the target job. Keep the final weights totaling 100 and retain the hard gates.

- **Backend / platform / infrastructure:** emphasize architecture, API/data contracts, code maintainability, tests, security, reliability, networking and CI/CD. Visual polish may be lower-weight, but API usability and error behavior still matter.
- **AI / ML / agent engineering:** emphasize data/model evaluation, reproducibility, agent/tool boundaries, prompt-injection resistance, observability, model/provider fallbacks, cost/latency controls and software engineering quality.
- **Frontend:** meaningfully score visual hierarchy, responsive behavior, accessibility, performance, state/error handling, browser/network integration and component tests. UI should not be ignored for roles that own it.
- **Full-stack:** balance user journeys, frontend/API integration, architecture, persistence, security, tests and end-to-end deployment.
- **Data engineering / analytics:** emphasize source lineage, correctness, schema evolution, data quality, reproducible pipelines, statistical validity, data access controls and observability.

## Interview questions the project should survive

1. What concrete user problem does this solve, and what is deliberately out of scope?
2. Trace one request or job from input through the system and back to an observable result.
3. Why this architecture/technology rather than a simpler alternative?
4. What are the three most important failure modes, and how are they detected/recovered?
5. Show a test that caught a real bug or protects a non-obvious invariant.
6. Which checks run in CI, what blocks a merge/release, and what remains manual?
7. What did you personally design, write, debug, test and deploy versus AI-generated or third-party work?
8. Which performance or quality claims are measured, under what conditions, and where is the raw evidence?
9. What would you change if traffic, data volume, cost or reliability requirements grew by 10x?
10. What is the most important limitation still present?

## Evidence rules

- Record score, evidence reference, reviewer confidence and unanswered questions per dimension.
- `NOT RUN` is different from `PASS`; explain why a check was not run.
- Label synthetic data, mock services and load tests as such.
- Performance metrics need baseline, environment, workload, sample size and measurement method.
- AI-generated code is not penalized merely because AI was used; unreviewed, unexplained, untested or unmaintainable output should be penalized under the relevant dimensions.
- Do not average away a critical security, data-loss, authorization or reproducibility problem.
