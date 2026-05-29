"""init / update / sync_src / base-protection round-trips on temp clones.

These lock down the safety behaviors found during review: update never clobbers
a user edit without a .rp-new, raises no false conflict when the template is
unchanged, is conservative when the state baseline is missing, and refreshes a
framework file the user did not touch.
"""

import os
import shutil
import tempfile
import unittest

import _util as u


class LifecycleCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rp-life-")
        self.proj = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.proj, "src"))
        with open(os.path.join(self.proj, "src", "a.py"), "w") as fh:
            fh.write("x = 1\n")
        self.clone = os.path.join(self.tmp, "clone")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fw_doc(self):
        return os.path.join(self.clone, "docs", "entrypoint.md")  # framework-owned

    def prj_doc(self):
        return os.path.join(self.clone, "docs", "project", "project-status.md")  # project-owned

    def test_init_writes_config_state_and_removes_marker(self):
        r = u.make_clone(self.clone, self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.clone, "researchpartner.config.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.clone, ".researchpartner-state.json")))
        self.assertFalse(os.path.isfile(os.path.join(self.clone, ".researchpartner-base")))
        self.assertEqual(u.guard(self.clone).returncode, 0)

    def test_update_idempotent(self):
        u.make_clone(self.clone, self.proj)
        r = u.update(self.clone)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("conflicts=0", r.stdout)

    def test_update_preserves_project_owned(self):
        u.make_clone(self.clone, self.proj)
        u.append(self.prj_doc(), "\nMY RESEARCH STATE\n")
        before = u.read(self.prj_doc())
        u.update(self.clone)
        self.assertEqual(u.read(self.prj_doc()), before)  # untouched

    def test_update_no_false_conflict_when_template_unchanged(self):
        u.make_clone(self.clone, self.proj)
        u.append(self.fw_doc(), "\nLOCAL EDIT\n")
        r = u.update(self.clone)
        self.assertIn("LOCAL EDIT", u.read(self.fw_doc()))            # edit preserved
        self.assertFalse(os.path.exists(self.fw_doc() + ".rp-new"))   # no spurious conflict
        self.assertIn("left=1", r.stdout)

    def test_update_conservative_when_state_missing(self):
        u.make_clone(self.clone, self.proj)
        u.append(self.fw_doc(), "\nLOCAL EDIT\n")
        os.remove(os.path.join(self.clone, ".researchpartner-state.json"))
        u.update(self.clone)
        self.assertIn("LOCAL EDIT", u.read(self.fw_doc()))            # not clobbered
        self.assertTrue(os.path.exists(self.fw_doc() + ".rp-new"))    # written for review

    def test_update_refreshes_unedited_framework_file(self):
        u.make_clone(self.clone, self.proj)
        tmpl = os.path.join(self.clone, "templates", "docs", "operations", "README.md.tmpl")
        u.append(tmpl, "\n<!-- upstream improvement -->\nUPSTREAM LINE\n")
        u.update(self.clone)
        self.assertIn("UPSTREAM LINE", u.read(os.path.join(self.clone, "docs", "operations", "README.md")))

    def test_src_mirror(self):
        u.make_clone(self.clone, self.proj, SRC_MIRROR_ENABLED="yes")
        self.assertTrue(os.path.isfile(os.path.join(self.clone, "src", "a.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.clone, "src", "MIRROR.md")))


class BaseProtectionCase(unittest.TestCase):
    def test_skip_git_does_not_bypass_base_protection(self):
        tmp = tempfile.mkdtemp(prefix="rp-base-")
        try:
            proj = os.path.join(tmp, "proj")
            os.makedirs(proj)
            clone = os.path.join(tmp, "clone")
            u.copy_base(clone)  # marker present, no git, no upstream
            cfg = u.write_config(clone, proj)
            # init with --skip-git but WITHOUT --force must refuse on the base
            r = u._run([os.path.join(clone, "scripts", "init.py"),
                        "--non-interactive", "--config", cfg, "--skip-git"])
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("BASE repo", r.stderr)
            self.assertFalse(os.path.isdir(os.path.join(clone, "docs")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
