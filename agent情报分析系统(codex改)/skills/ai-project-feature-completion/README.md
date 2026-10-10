# AI做项目功能补全 Skill

A repository-ready skill for reverse-engineering project requirements, mapping capabilities to technical stacks and job competencies, checking real-world environment/resource constraints, implementing with AI in bounded iterations, independently auditing changes, and producing truthful portfolio evidence.

## Install

Copy this folder into the skill directory supported by your coding agent. A common layout is:

```text
.agents/skills/ai-project-feature-completion/
  SKILL.md
  README.md
  SOURCES.md
  references/
  templates/
  scripts/
```

Add a short pointer in the existing project instructions (for example `AGENTS.md`) rather than creating competing root policies. Adapt the path to the specific tool's documented skill mechanism.

## Suggested usage

1. **Before a new project:** fill `templates/REVERSE_ENGINEERING_WORKSHEET.md` and `templates/JOB_COMPETENCY_MATRIX.md`; research reference implementations; complete feasibility/resource checks; then write the product brief and architecture.
2. **For an existing project:** begin with a read-only audit and record the actual source/CI/test baseline before edits.
3. **For each implementation task:** use `templates/CHANGE_CONTRACT.md`, make one bounded change, run the verification ladder and inspect the final diff.
4. **For AI iterations:** record real research, implementation and independent review actions in `templates/AI_ITERATION_LOG.md`. Never claim a model was used if it was not actually invoked.
5. **Before release:** complete `templates/RELEASE_AUDIT.md`; hard-gate failures override all scores.
6. **For interviews:** complete `templates/RESUME_EVIDENCE.md` with evidence-backed claims and use `references/scorecard.md` against the target role.

## Optional document presence check

```bash
python scripts/audit_artifacts.py /path/to/project --tier portfolio
```

Supported tiers: `experiment`, `portfolio`, `production-like`, `production`. The script checks selected documents and obvious placeholders only; it does not inspect all source code, execute tests, scan vulnerabilities, or certify enterprise readiness.

## Core principles

- Reverse-engineer from user problems and role competencies; do not build a technology showcase with no acceptance criterion.
- Map requirements to modules, interfaces, tests and evidence.
- Check CPU/RAM/disk/GPU/VRAM, operating system, native dependencies, network access, data permissions, cost and deployment capability before committing to a stack.
- Treat AI-generated output as a draft that must be understood, reviewed, tested and maintained.
- Keep independent reviewers honest: record real calls, preserve disagreements and require evidence.
- UI weight depends on role; it is central for frontend roles but generally less dominant for backend/platform roles.
- No unsubstantiated “enterprise-grade” labels or invented resume metrics.
- One failed mandatory gate blocks release regardless of weighted score.
