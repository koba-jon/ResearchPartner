"""Render the leanest and all-on configurations; assert clean output + toggles."""

import os
import re
import shutil
import tempfile
import unittest

import _util as u

TOKEN_RE = re.compile(r"\{\{[A-Z_]+\}\}")
MARKER_RE = re.compile(r"<!--\s*(?:if:|else|endif|include:)")


def scan(docs_dir):
    tokens, markers = [], []
    for dp, _, fs in os.walk(docs_dir):
        for name in fs:
            if not name.endswith(".md"):
                continue
            text = u.read(os.path.join(dp, name))
            rel = os.path.relpath(os.path.join(dp, name), docs_dir)
            if TOKEN_RE.search(text):
                tokens.append(rel)
            if MARKER_RE.search(text):
                markers.append(rel)
    return tokens, markers


class MatrixCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rp-matrix-")
        self.proj = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.proj, "src"))
        with open(os.path.join(self.proj, "src", "a.py"), "w") as fh:
            fh.write("x = 1\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _render(self, name, **over):
        clone = os.path.join(self.tmp, name)
        r = u.make_clone(clone, self.proj, **over)
        self.assertEqual(r.returncode, 0, r.stderr)
        tokens, markers = scan(os.path.join(clone, "docs"))
        self.assertEqual(tokens, [], "unresolved tokens in: %s" % tokens)
        self.assertEqual(markers, [], "leftover conditional markers in: %s" % markers)
        self.assertEqual(u.guard(clone).returncode, 0)
        return clone

    def test_leanest(self):
        clone = self._render("lean", SRC_MIRROR_ENABLED="no", ENABLE_AUTO_MODE="no",
                             GENERATE_MANUAL="no", ENABLE_PUBLISH_STEP="no")
        self.assertFalse(os.path.exists(os.path.join(clone, "docs", "operations", "auto-mode.md")))
        self.assertFalse(os.path.exists(os.path.join(clone, "GETTING_STARTED.md")))
        pf = u.read(os.path.join(clone, "docs", "operations", "prompt-factory.md"))
        self.assertNotIn("Publish (optional closing step)", pf)
        # First-session setup: data bootstrap is always offered; localization is not
        # (this is an English clone).
        ep = u.read(os.path.join(clone, "docs", "entrypoint.md"))
        self.assertIn("First-session setup", ep)
        self.assertNotIn("Localize the docs", ep)
        self.assertIn("4.7 Project Bootstrap", pf)
        self.assertNotIn("4.6 Docs Localization", pf)

    def test_all_on(self):
        clone = self._render("all", SRC_MIRROR_ENABLED="yes", ENABLE_AUTO_MODE="yes",
                             GENERATE_MANUAL="yes", ENABLE_PUBLISH_STEP="yes",
                             COMPUTE_ENV="colab",
                             COMPUTE_DRIVE="/content/drive/MyDrive/X",
                             EXPERIMENT_UNIT_LABEL="Wave", ANALYSIS_RECORD_LABEL="Theme")
        self.assertTrue(os.path.exists(os.path.join(clone, "docs", "operations", "auto-mode.md")))
        self.assertTrue(os.path.exists(os.path.join(clone, "GETTING_STARTED.md")))
        pf = u.read(os.path.join(clone, "docs", "operations", "prompt-factory.md"))
        self.assertIn("Publish (optional closing step)", pf)

    def test_localization_render(self):
        # A non-English clone gets both first-session offers and both recipes.
        clone = self._render("ja", DOCS_LANG="Japanese")
        ep = u.read(os.path.join(clone, "docs", "entrypoint.md"))
        self.assertIn("First-session setup", ep)
        self.assertIn("Localize the docs", ep)
        pf = u.read(os.path.join(clone, "docs", "operations", "prompt-factory.md"))
        self.assertIn("4.6 Docs Localization", pf)
        self.assertIn("4.7 Project Bootstrap", pf)

    def test_every_mode_has_linked_file(self):
        # 8 modes <-> 8 protocol files <-> every one linked from the router.
        clone = self._render("modes", ENABLE_AUTO_MODE="yes")
        om = u.read(os.path.join(clone, "docs", "operations", "operation-modes.md"))
        for m in ("investigate", "design", "implement", "experiment",
                  "analysis", "write", "auto", "maintenance"):
            rel = "docs/operations/%s-mode.md" % m
            self.assertTrue(os.path.exists(os.path.join(clone, *rel.split("/"))),
                            "missing mode file: %s" % rel)
            self.assertIn(rel, om, "operation-modes.md does not link %s" % rel)


if __name__ == "__main__":
    unittest.main()
