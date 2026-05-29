#!/usr/bin/env python3
"""Base-side lint: validate templates, manifest, and token sanity.

Run from the ResearchPartner BASE repo (where templates/ lives and there is no
rendered docs/). Invoked by `make lint-base` and by the pre-commit hook when the
.researchpartner-base marker is present.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _framework as fw  # noqa: E402


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems = fw.lint_templates(root) + fw.validate_manifest(root)
    if not problems:
        print("Base template lint OK")
        return 0
    sys.stderr.write("Base template lint FAILED\n")
    for p in problems:
        sys.stderr.write("- %s\n" % p)
    return 1


if __name__ == "__main__":
    sys.exit(main())
