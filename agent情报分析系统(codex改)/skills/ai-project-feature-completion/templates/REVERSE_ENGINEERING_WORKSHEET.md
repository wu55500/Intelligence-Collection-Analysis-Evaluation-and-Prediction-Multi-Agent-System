# Reverse-Engineering Worksheet

## A. Goal and context
- Project name:
- Primary target role / seniority:
- Secondary role (optional):
- Target user and problem:
- Existing workaround / competing solutions:
- What should a reviewer be able to verify in 5 minutes?
- Delivery context (local, phone-only, cloud, portfolio deploy, production):
- Hard constraints and non-goals:

## B. Reference reconnaissance
| Reference/repo/docs | Version/commit/date inspected | License | What was actually inspected | Useful design | Risk/limitation | Adopt / adapt / reject and why |
|---|---|---|---|---|---|---|

Do not infer code quality from stars, a polished website, or README claims alone. For copied/adapted code, confirm license obligations and record provenance.

## C. Capability decomposition
| Capability ID | User / trigger | Input | Output/state | Failure/edge cases | Business reason | Acceptance test | Priority |
|---|---|---|---|---|---|---|---|

## D. Module and interface mapping
| Capability ID | Module/owner | API/event/contract | Data entity | Algorithm/rule | Dependencies | Test type | Evidence expected |
|---|---|---|---|---|---|---|---|

## E. Technology-to-function-to-role map
| Need | Candidate technology/concept | Simpler alternative | Relevant discipline/role | Why selected | Trade-off | What I must be able to explain in interview |
|---|---|---|---|---|---|---|

Include software engineering, networking, databases, OS/runtime, security, QA, statistics/experimentation, data/ML/LLM, DevOps/SRE, product design and technical writing only as applicable. A technology is not a requirement by itself.

## F. Feasibility and resource preflight
| Component/requirement | Status FEASIBLE / CONDITIONAL / NOT_FEASIBLE / UNKNOWN | CPU/RAM/disk/GPU/VRAM | OS/runtime/container | Network/API/data access | Cost/latency/quotas | Fallback or experiment | Owner/date |
|---|---|---|---|---|---|---|---|

Explicitly check: device constraints; whether local execution is realistic; cloud/remote runner needs; GPU type and VRAM; model size/quantization; native libraries; Docker/virtualization; network/DNS/TLS/proxy assumptions; API credentials/rate limits; privacy/license; deployment and operation responsibilities.

## G. Decision gate
- Requirements impossible or unjustified at current constraints:
- Scope reduction/options considered:
- Highest-risk assumptions to test cheaply:
- Go / revise / stop decision and rationale:
- Reviewer and evidence:
