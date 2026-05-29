"""lint_base coverage: the clean base passes; a single-brace token leak is caught.

Closes a gap: lint_base.py (and thus _framework.lint_templates) previously had a
helper in _util but no test driving it, so the ${TOKEN} single-brace leak class
shipped twice undetected.
"""

import os
import shutil
import tempfile
import unittest

import _util as u


class LintBaseCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rp-lint-")
        self.base = os.path.join(self.tmp, "base")
        u.copy_base(self.base)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_base_passes(self):
        r = u.lint_base(self.base)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_single_brace_token_leak_is_flagged(self):
        tmpl = os.path.join(self.base, "templates", "docs", "concepts", "glossary.md.tmpl")
        u.append(tmpl, "\nSee ${REPO_VAR_BRACE}/src for the mirror.\n")
        r = u.lint_base(self.base)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("single-brace token leak", r.stderr)


if __name__ == "__main__":
    unittest.main()
