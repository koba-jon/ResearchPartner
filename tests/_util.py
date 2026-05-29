"""Shared helpers for the ResearchPartner test suite (stdlib only).

Tests exercise the real entry points: pure-function units import the library
directly; lifecycle/guard tests copy the base into a temp dir and drive the
clone's own scripts via subprocess (so init/update/guard run exactly as a user
would invoke them).
"""

import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")

BASE_CONFIG = {
    "PROJECT_NAME": "Test Project",
    "USER_NAME": "Tester",
    "CHAT_LANG": "English",
    "DOCS_LANG": "English",
    "CODE_LANG": "English",
    "COMPUTE_ENV": "local-cpu",
    "COMPUTE_DRIVE": "",
    "SRC_MIRROR_ENABLED": "no",
    "ENABLE_AUTO_MODE": "no",
    "GENERATE_MANUAL": "no",
    "EXPERIMENT_UNIT_LABEL": "Experiment",
    "ANALYSIS_RECORD_LABEL": "Note",
}


def copy_base(dest):
    """Copy the base repo into dest (excluding git/cache/tests/CI)."""
    shutil.copytree(REPO, dest, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "tests", ".github", "*.rp-new"))
    return dest


def write_config(clone, project_root, path=None, **overrides):
    cfg = dict(BASE_CONFIG)
    cfg["PROJECT_ROOT"] = project_root
    cfg["CLAUDE_DIR"] = os.path.join(project_root, "claude")
    cfg["FRAMEWORK_REPO_DIR"] = clone
    cfg.update(overrides)
    path = path or os.path.join(clone, "_test.config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return path


def _run(args, **kw):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True, **kw)


def init_clone(clone, config_path, *extra):
    return _run([os.path.join(clone, "scripts", "init.py"),
                 "--non-interactive", "--config", config_path,
                 "--skip-git", "--force", *extra])


def make_clone(dest, project_root, **overrides):
    """Copy the base, write a config, run init non-interactively. Returns the
    init CompletedProcess; the configured clone is at `dest`."""
    copy_base(dest)
    cfgp = write_config(dest, project_root, **overrides)
    return init_clone(dest, cfgp)


def guard(instance, *extra):
    return _run([os.path.join(instance, "scripts", "check_docs_consistency.py"),
                 "--instance", instance, *extra])


def update(clone, *extra):
    return _run([os.path.join(clone, "scripts", "update.py"),
                 "--instance", clone, *extra])


def lint_base(repo):
    return _run([os.path.join(repo, "scripts", "lint_base.py")])


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def append(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)
