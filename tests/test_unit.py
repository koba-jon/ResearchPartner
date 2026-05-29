"""Unit tests for the engine, config layer, and manifest (pure functions)."""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import _framework as f  # noqa: E402


def ctx(**over):
    base = dict(
        f.DEFAULT_CONFIG, PROJECT_NAME="Acme Vision", USER_NAME="Alex",
        PROJECT_ROOT="/p/acme", FRAMEWORK_REPO_DIR="/p/acme/RP",
        CLAUDE_DIR="/p/acme/claude")
    base.update(over)
    return f.derive(base)


class TestTokens(unittest.TestCase):
    def test_basic_and_brace(self):
        c = ctx()
        out = f.render_str('v {{PROJECT_VAR}}="{{PROJECT_ROOT}}" p {{REPO_VAR_BRACE}}/src', c)
        self.assertEqual(out, 'v ACME_VISION_ROOT="/p/acme" p ${ACME_VISION_DOCS}/src')

    def test_triple_brace_form(self):
        self.assertEqual(f.render_str("see ${{{PROJECT_VAR}}}/x", ctx()),
                         "see ${ACME_VISION_ROOT}/x")

    def test_unknown_token_survives_for_detection(self):
        self.assertEqual(f.find_unresolved("a {{MISSING}} b"), [(1, "MISSING")])

    def test_shell_var_disjoint_from_token(self):
        self.assertEqual(f.find_unresolved("${REAL_SHELL}/x"), [])


class TestConditionals(unittest.TestCase):
    def test_block_if_else(self):
        t = "a\n<!-- if:SRC_MIRROR_ENABLED=yes -->\non\n<!-- else -->\noff\n<!-- endif -->\nb"
        self.assertEqual(f.render_str(t, ctx(SRC_MIRROR_ENABLED="yes")), "a\non\nb")
        self.assertEqual(f.render_str(t, ctx(SRC_MIRROR_ENABLED="no")), "a\noff\nb")

    def test_inline_partial(self):
        line = "X.<!-- if:SRC_MIRROR_ENABLED=yes --> Y.<!-- endif --> Z."
        self.assertEqual(f.render_str(line, ctx(SRC_MIRROR_ENABLED="yes")), "X. Y. Z.")
        self.assertEqual(f.render_str(line, ctx(SRC_MIRROR_ENABLED="no")), "X. Z.")

    def test_inline_whole_line_dropped(self):
        t = "| h |\n<!-- if:ENABLE_AUTO_MODE=yes -->| row |<!-- endif -->\n| z |"
        self.assertEqual(f.render_str(t, ctx(ENABLE_AUTO_MODE="no")), "| h |\n| z |")
        self.assertEqual(f.render_str(t, ctx(ENABLE_AUTO_MODE="yes")), "| h |\n| row |\n| z |")

    def test_boolean_form(self):
        self.assertEqual(f.render_str("<!-- if:GENERATE_MANUAL -->M<!-- endif -->",
                                      ctx(GENERATE_MANUAL="yes")), "M")

    def test_unclosed_raises(self):
        with self.assertRaises(f.RenderError):
            f.render_str("<!-- if:X=y -->\nz", ctx())

    def test_stray_endif_raises(self):
        with self.assertRaises(f.RenderError):
            f.render_str("z\n<!-- endif -->", ctx())

    def test_glued_marker_leaves_residue_for_lint(self):
        # if-with-content on one line, endif glued ahead of next content: neither
        # valid block nor valid inline. The leftover marker is what lint catches.
        bad = "<!-- if:A=yes -->one\n<!-- endif --><!-- if:B=yes -->two\n<!-- endif -->tail"
        try:
            out = f.render_str(bad, ctx())
        except f.RenderError:
            return  # also an acceptable failure mode
        self.assertTrue(re.search(r"<!--\s*(if:|endif)", out),
                        "a glued marker must either raise or leave a detectable residue")


class TestIncludes(unittest.TestCase):
    def setUp(self):
        self.frags = {"_fragments/h.txt": '{{PROJECT_VAR}}="{{PROJECT_ROOT}}"'}

    def resolver(self, p):
        return self.frags.get(p)

    def test_include_expands(self):
        out = f.render_str("a\n<!-- include: _fragments/h.txt -->\nb", ctx(), self.resolver)
        self.assertEqual(out, 'a\nACME_VISION_ROOT="/p/acme"\nb')

    def test_missing_include_raises(self):
        with self.assertRaises(f.RenderError):
            f.render_str("<!-- include: _fragments/nope.txt -->", ctx(), self.resolver)

    def test_parent_path_rejected(self):
        with self.assertRaises(f.RenderError):
            f.render_str("<!-- include: ../secret.txt -->", ctx(), self.resolver)


class TestConfig(unittest.TestCase):
    def test_shell_ident(self):
        self.assertEqual(f.shell_ident("Acme Vision"), "ACME_VISION")
        self.assertEqual(f.shell_ident("3D-Recon"), "_3D_RECON")
        self.assertEqual(f.shell_ident("!!!"), "PROJECT")

    def test_derived_vars(self):
        c = ctx()
        self.assertEqual(c["PROJECT_VAR"], "ACME_VISION_ROOT")
        self.assertEqual(c["REPO_VAR"], "ACME_VISION_DOCS")
        self.assertEqual(c["ROLE_TERM"], "Research Partner")

    def test_docs_ascii_derived_from_lang(self):
        self.assertEqual(ctx(DOCS_LANG="English")["DOCS_LANG_IS_ASCII"], "yes")
        self.assertEqual(ctx(DOCS_LANG="Japanese")["DOCS_LANG_IS_ASCII"], "no")

    def test_docs_ascii_explicit_wins(self):
        self.assertEqual(ctx(DOCS_LANG="Japanese", DOCS_LANG_IS_ASCII="yes")["DOCS_LANG_IS_ASCII"], "yes")

    def test_validate_flags_bad_enum(self):
        bad = dict(BASE_REQUIRED(), COMPUTE_ENV="cloud")
        self.assertTrue(any("COMPUTE_ENV" in p for p in f.validate_config(bad)))

    def test_validate_requires_colab_drive(self):
        bad = dict(BASE_REQUIRED(), COMPUTE_ENV="colab", COMPUTE_DRIVE="")
        self.assertTrue(any("COMPUTE_DRIVE" in p for p in f.validate_config(bad)))

    def test_var_name_override(self):
        c = ctx(REPO_VAR="AI_SCIENTIST_GSAD")
        self.assertEqual(c["REPO_VAR"], "AI_SCIENTIST_GSAD")
        self.assertEqual(c["REPO_VAR_BRACE"], "${AI_SCIENTIST_GSAD}")

    def test_var_name_blank_derives(self):
        self.assertEqual(ctx(REPO_VAR="")["REPO_VAR"], "ACME_VISION_DOCS")

    def test_validate_rejects_bad_var_name(self):
        bad = dict(BASE_REQUIRED(), REPO_VAR="not valid")
        self.assertTrue(any("shell-safe" in p for p in f.validate_config(bad)))


def BASE_REQUIRED():
    return dict(f.DEFAULT_CONFIG, PROJECT_NAME="P", USER_NAME="U", PROJECT_ROOT="/p",
                FRAMEWORK_REPO_DIR="/p/r", CLAUDE_DIR="/p/c")


class TestGlobMatcher(unittest.TestCase):
    def test_star_one_segment(self):
        self.assertTrue(f._glob_match("docs/*.md", "docs/a.md"))
        self.assertFalse(f._glob_match("docs/*", "docs/a/b.md"))

    def test_double_star_spans_dirs(self):
        self.assertTrue(f._glob_match("docs/**", "docs/a/b/c.md"))
        self.assertTrue(f._glob_match("docs/**", "docs/a.md"))

    def test_exact(self):
        self.assertTrue(f._glob_match("Makefile", "Makefile"))
        self.assertFalse(f._glob_match("Makefile", "Makefile.bak"))


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.m = f.load_manifest(os.path.join(REPO, "ownership.json"))

    def test_most_specific_wins(self):
        self.assertEqual(self.m.classify("docs/entrypoint.md"), "framework")
        # catch-all docs/** -> project
        self.assertEqual(self.m.classify("docs/concepts/core-concepts.md"), "project")

    def test_conditional_active(self):
        on = dict(f.DEFAULT_CONFIG, ENABLE_AUTO_MODE="yes")
        off = dict(f.DEFAULT_CONFIG, ENABLE_AUTO_MODE="no")
        self.assertTrue(self.m.is_active("docs/operations/auto-mode.md", on))
        self.assertFalse(self.m.is_active("docs/operations/auto-mode.md", off))


if __name__ == "__main__":
    unittest.main()
