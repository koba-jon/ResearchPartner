"""Guard behavior on a rendered clone: a good clone passes; each defect class fails."""

import os
import shutil
import tempfile
import unittest

import _util as u


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rp-guard-")
        self.proj = os.path.join(self.tmp, "proj")
        os.makedirs(self.proj)
        self.clone = os.path.join(self.tmp, "clone")
        r = u.make_clone(self.clone, self.proj)
        self.assertEqual(r.returncode, 0, "init failed: " + r.stderr)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def doc(self, rel):
        return os.path.join(self.clone, "docs", rel)

    def test_good_clone_passes(self):
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_mirror_drift_fails(self):
        ep = self.doc("entrypoint.md")
        u.append(ep, "")  # no-op; mutate the mirrored block instead
        text = u.read(ep).replace("You are the dedicated Research Partner",
                                  "You are the SO DIFFERENT Research Partner", 1)
        with open(ep, "w", encoding="utf-8") as fh:
            fh.write(text)
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 1)
        self.assertIn("mirror drift", r.stderr)

    def test_dangling_backtick_fails(self):
        u.append(self.doc("project/project-status.md"),
                 "\nSee `docs/operations/does-not-exist.md`.\n")
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 1)
        self.assertIn("does-not-exist.md", r.stderr)

    def test_non_ascii_letters_fail_when_ascii(self):
        u.append(self.doc("project/project-status.md"), "\nPrivet: Привет\n")
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 1)
        self.assertIn("non-ASCII letters", r.stderr)

    def test_missing_required_file_fails(self):
        os.remove(self.doc("operations/rules/forbidden-actions.md"))
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing required file", r.stderr)

    def test_router_break_fails(self):
        readme = self.doc("operations/rules/README.md")
        text = u.read(readme).replace("forbidden-actions.md", "FORBIDDEN.md")
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write(text)
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 1)
        self.assertIn("rules README", r.stderr)

    def test_titled_link_passes(self):
        # a markdown link with a title must not be misread as a missing target
        u.append(self.doc("project/project-status.md"),
                 '\nSee [the numbers](../evaluation/comparison.md "metric table").\n')
        r = u.guard(self.clone)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class JapaneseDocsCase(unittest.TestCase):
    """A non-ASCII-docs clone must NOT be flagged for its script."""

    def test_japanese_docs_pass(self):
        tmp = tempfile.mkdtemp(prefix="rp-ja-")
        try:
            proj = os.path.join(tmp, "proj")
            os.makedirs(proj)
            clone = os.path.join(tmp, "clone")
            # DOCS_LANG_IS_ASCII omitted on purpose -> derived "no" from DOCS_LANG
            r = u.make_clone(clone, proj, DOCS_LANG="Japanese", PROJECT_NAME="Acme")
            self.assertEqual(r.returncode, 0, r.stderr)
            u.append(os.path.join(clone, "docs", "project", "project-status.md"),
                     "\nこれは日本語です。\n")
            g = u.guard(clone)
            self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
