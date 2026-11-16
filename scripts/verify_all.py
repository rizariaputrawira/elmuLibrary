#!/usr/bin/env python3
"""Unified verification runner for the Karpathy LLM Wiki.

Executes check_frontmatter.py, lint_wiki.py, and check_evidence.py in order
against a target project root and returns 0 only if all checks pass.

Usage: verify_all.py [project-root]
Defaults: project-root is current directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_evidence
import check_frontmatter
import lint_wiki


def main(argv: list[str]) -> int:
    root = str(Path(argv[1]).resolve()) if len(argv) > 1 else str(Path.cwd())
    checks = [
        ("check_frontmatter", check_frontmatter.main),
        ("lint_wiki", lint_wiki.main),
        ("check_evidence", check_evidence.main),
    ]

    failures: list[str] = []
    for name, fn in checks:
        rc = fn([name, root])
        if rc != 0:
            failures.append(name)
        print()

    if failures:
        print(f"Verification FAILED: {', '.join(failures)}")
        return 1
    print("Verification PASSED: all 3 checks succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
