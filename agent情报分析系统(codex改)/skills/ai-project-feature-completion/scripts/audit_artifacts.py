#!/usr/bin/env python3
"""Check presence of project-governance artifacts and obvious placeholders.
This does not parse source code, run tests, scan vulnerabilities, or certify a project.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import sys

BASELINE_DOCS = [
    "PROJECT_BRIEF.md",
    "ARCHITECTURE.md",
    "TEST_STRATEGY.md",
    "SECURITY_MODEL.md",
]
TIER_FILES = {
    "experiment": [],
    "portfolio": ["docs/RESUME_EVIDENCE.md"],
    "production-like": ["docs/CHANGE_CONTRACT.md", "docs/RUNBOOK.md", "docs/RELEASE_AUDIT.md"],
    "production": ["docs/CHANGE_CONTRACT.md", "docs/RUNBOOK.md", "docs/RELEASE_AUDIT.md", "docs/AI_ITERATION_LOG.md"],
}
PLACEHOLDER_PATTERNS = [
    re.compile(r"\b(TODO|TBD|FIXME|FILL ME|REPLACE ME)\b", re.IGNORECASE),
    re.compile(r"\[\s*(insert|add|fill in|describe|your )[^\]]*\]", re.IGNORECASE),
]
EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "coverage"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="path to project root")
    parser.add_argument("--tier", choices=sorted(TIER_FILES), default="portfolio")
    parser.add_argument("--docs-dir", default="docs", help="documentation directory relative to project root")
    args = parser.parse_args()
    root = args.project.resolve()
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}")
        return 2

    docs_dir = args.docs_dir.rstrip("/")
    required = ["README.md"] + [f"{docs_dir}/{name}" for name in BASELINE_DOCS]
    required += [f"{docs_dir}/{Path(name).name}" for name in TIER_FILES[args.tier]]
    missing = [rel for rel in required if not (root / rel).is_file()]
    print(f"Project: {root}\nTier profile: {args.tier}\n")
    if missing:
        print("MISSING ARTIFACTS:")
        for rel in missing:
            print(f"  - {rel}")
    else:
        print("Required artifact presence: PASS")

    flagged = []
    for base in (root / "docs", root / args.docs_dir):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in {".md", ".txt", ".yaml", ".yml"}:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                if any(p.search(line) for p in PLACEHOLDER_PATTERNS):
                    flagged.append((path.relative_to(root), line_no, line.strip()[:180]))
    if flagged:
        print("\nPOSSIBLE PLACEHOLDERS (review manually; some may be intentional):")
        for path, line_no, line in flagged:
            print(f"  - {path}:{line_no}: {line}")
    else:
        print("No obvious placeholder patterns found in scanned docs.")

    if missing:
        print("\nRESULT: PARTIAL — missing artifacts. This is only a documentation check.")
        return 1
    if flagged:
        print("\nRESULT: REVIEW — possible placeholders found. This is only a documentation check.")
        return 0
    print("\nRESULT: ARTIFACT PRESENCE CHECK PASSED; this is NOT a software-quality/security certification.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
