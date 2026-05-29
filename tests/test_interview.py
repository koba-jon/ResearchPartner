"""The interactive interview (init.py): auto-derivations and confirm-or-edit.

The non-interactive config path skips interview(), so these run the real script
with `--print-config` and piped stdin — the only coverage of the interview's
auto-derivation (src/ -> mirror, docs language -> localization flag) and confirm-or-edit flow.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _util as u


def run_interview(answers, repo=u.REPO):
    """Feed `answers` (line strings) to `init.py --print-config` and return
    (resolved_config_dict_or_None, CompletedProcess). --print-config runs the
    interview, prints the resolved config as JSON, and writes nothing."""
    stdin = "".join(a + "\n" for a in answers)
    r = subprocess.run(
        [sys.executable, os.path.join(repo, "scripts", "init.py"), "--print-config"],
        input=stdin, capture_output=True, text=True)
    cfg = json.loads(r.stdout[r.stdout.index("{"):]) if "{" in r.stdout else None
    return cfg, r


class InterviewCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rp-interview-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _proj(self, name, *, src=False, py=False):
        p = os.path.join(self.tmp, name)
        os.makedirs(p)
        if src:
            os.makedirs(os.path.join(p, "src"))
            with open(os.path.join(p, "src", "a.py"), "w") as fh:
                fh.write("x = 1\n")
        if py:
            with open(os.path.join(p, "main.py"), "w") as fh:
                fh.write("x = 1\n")
        return p

    # Phase 1 head is always: PROJECT_ROOT (no -> type path), CLAUDE_DIR (accept),
    # COMPUTE_ENV (accept default local-cpu).
    def _head(self, proj):
        return ["no", proj, "yes", ""]

    def test_mirror_auto_enabled_when_src_exists(self):
        """src/ present -> mirror auto-on, no question; and the 'no'->path
        override for the project root is honoured."""
        proj = self._proj("withsrc", src=True)
        cfg, r = run_interview(self._head(proj) + ["yes", "Tester", "", "", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cfg["PROJECT_ROOT"], proj)
        self.assertEqual(cfg["SRC_MIRROR_ENABLED"], "yes")
        self.assertNotIn("Mirror your source", r.stdout)  # no longer a question

    def test_mirror_off_when_code_but_no_src(self):
        """Code present (a .py at root) but no src/ dir -> mirror auto-off
        (sync_src mirrors PROJECT_ROOT/src specifically)."""
        proj = self._proj("nosrc", py=True)
        cfg, r = run_interview(self._head(proj) + ["yes", "Tester", "", "", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cfg["SRC_MIRROR_ENABLED"], "no")

    def test_docs_lang_english_flag_derived(self):
        """DOCS_LANG drives the derived DOCS_LANG_IS_ENGLISH flag (Japanese ->
        no), which gates the one-time localization offer. The removed
        DOCS_LANG_IS_ASCII flag is gone."""
        proj = self._proj("jp", py=True)
        cfg, r = run_interview(self._head(proj) + ["yes", "Tester", "", "Japanese", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cfg["DOCS_LANG"], "Japanese")
        self.assertEqual(cfg["DOCS_LANG_IS_ENGLISH"], "no")
        self.assertNotIn("DOCS_LANG_IS_ASCII", cfg)

    def test_confirm_or_edit_overrides_project_name(self):
        """Answering 'no' to the project-name confirm collects a typed value."""
        proj = self._proj("withsrc", src=True)
        cfg, r = run_interview(self._head(proj) + ["no", "Custom Name", "Tester", "", "", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cfg["PROJECT_NAME"], "Custom Name")

    def test_no_code_triggers_intent_interview(self):
        """An empty workspace has no code -> the intent interview runs and the
        mirror stays off."""
        proj = self._proj("empty")
        cfg, r = run_interview(
            self._head(proj) + ["Anomaly", "PyTorch", "Goal", "Step",
                                 "yes", "Tester", "", "", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cfg["INTENT_DOMAIN"], "Anomaly")
        self.assertEqual(cfg["INTENT_FIRST_STEP"], "Step")
        self.assertEqual(cfg["SRC_MIRROR_ENABLED"], "no")

    def test_defaults_not_asked(self):
        """GENERATE_MANUAL and ENABLE_AUTO_MODE are on by default and not asked."""
        proj = self._proj("withsrc", src=True)
        cfg, r = run_interview(self._head(proj) + ["yes", "Tester", "", "", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cfg["GENERATE_MANUAL"], "yes")
        self.assertEqual(cfg["ENABLE_AUTO_MODE"], "yes")
        self.assertNotIn("Generate a GETTING_STARTED", r.stdout)
        self.assertNotIn("Enable Auto mode", r.stdout)


if __name__ == "__main__":
    unittest.main()
