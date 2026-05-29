#!/usr/bin/env python3
"""Mirror source code from PROJECT_ROOT into the clone's src/.

Why a mirror: PROJECT_ROOT is the (often non-git) workspace where code, data and
checkpoints live; the clone is the git repo holding the shared docs. Mirroring a
read-only copy of the code into the clone lets the Research Partner read current
code via the docs repo (and lets reviewers see code + docs together) without ever
editing the mirror directly.

Policy: content-hash compare, copy only changed files, never delete unless
--prune, never copy data/checkpoints/caches. Only runs when SRC_MIRROR_ENABLED=yes.
"""

import argparse
import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _framework as fw  # noqa: E402

# Files/dirs never mirrored (heavy or environment-specific).
_SKIP_DIRS = {
    "__pycache__", ".git", ".ipynb_checkpoints", ".mypy_cache", ".pytest_cache",
    "checkpoints", "data", "datasets", "wandb",
}
_SKIP_EXT = {".pyc", ".pyo", ".so", ".o", ".pt", ".pth", ".ckpt", ".npy", ".npz"}
_SKIP_NAMES = {".DS_Store"}


def _hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_source(src_root):
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            if name in _SKIP_NAMES:
                continue
            if os.path.splitext(name)[1].lower() in _SKIP_EXT:
                continue
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, src_root).replace(os.sep, "/")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mirror code into the clone's src/")
    parser.add_argument("--instance", default=".", help="clone directory")
    parser.add_argument("--src-subdir", default="src",
                        help="subdirectory of PROJECT_ROOT to mirror (default src)")
    parser.add_argument("--prune", action="store_true",
                        help="delete mirror files that no longer exist in the source")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.instance)
    cfg_path = os.path.join(root, fw.CONFIG_FILE)
    if not os.path.isfile(cfg_path):
        fw.die("no %s found in %s — run init.py first" % (fw.CONFIG_FILE, root))
    cfg = fw.load_config(cfg_path)

    if not fw.truthy(cfg.get("SRC_MIRROR_ENABLED", "no")):
        fw.log("SRC_MIRROR_ENABLED is not 'yes' — nothing to mirror.")
        return 0

    project_root = cfg.get("PROJECT_ROOT", "")
    src_root = os.path.join(project_root, args.src_subdir)
    if not os.path.isdir(src_root):
        fw.die("source directory not found: %s" % src_root)
    dest_root = os.path.join(root, "src")

    copied, updated, unchanged, pruned = [], [], [], []
    source_rels = set()
    for rel in _iter_source(src_root):
        source_rels.add(rel)
        src = os.path.join(src_root, rel)
        dst = os.path.join(dest_root, rel)
        if not os.path.isfile(dst):
            copied.append(rel)
        elif _hash(src) != _hash(dst):
            updated.append(rel)
        else:
            unchanged.append(rel)
            continue
        if not args.dry_run:
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copy2(src, dst)

    if args.prune and os.path.isdir(dest_root):
        for rel in _iter_source(dest_root):
            if rel == "MIRROR.md":
                continue
            if rel not in source_rels:
                pruned.append(rel)
                if not args.dry_run:
                    os.remove(os.path.join(dest_root, rel))

    fw.log("Mirror %s -> %s" % (src_root, dest_root))
    fw.log("  copied=%d updated=%d unchanged=%d pruned=%d%s"
           % (len(copied), len(updated), len(unchanged), len(pruned),
              " (dry-run)" if args.dry_run else ""))

    if not args.dry_run:
        manifest = (
            "# Source Mirror\n\n"
            "This directory is a **read-only mirror** of `%s/%s`, produced by "
            "`make sync-src`. Do not edit files here directly; edit the source in "
            "PROJECT_ROOT and re-run the mirror (operational constraint: src mirror sync).\n\n"
            "- Source: `%s`\n- Files mirrored: %d\n"
            % (cfg.get("PROJECT_VAR", "PROJECT_ROOT"), args.src_subdir,
               src_root, len(source_rels))
        )
        fw.write_text(os.path.join(dest_root, "MIRROR.md"), manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
