#!/usr/bin/env python3
"""Re-render framework-owned files after pulling framework updates.

Typical use, in a configured clone, after `git merge upstream/main`:

    python3 scripts/update.py        # or: make update

Re-renders ONLY framework-owned (and active-conditional) outputs from the
current templates. Project-owned files (your research state) are never touched.
If a framework file was edited locally since the last render, the new version is
written to ``<file>.rp-new`` and a warning is printed instead of clobbering your
edit (compare and merge, then delete the .rp-new). Pass --force to overwrite
local edits directly.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _framework as fw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    p = argparse.ArgumentParser(description="Re-render framework-owned files")
    p.add_argument("--instance", default=ROOT, help="clone directory (default: this repo)")
    p.add_argument("--force", action="store_true",
                   help="overwrite locally-modified framework files instead of writing .rp-new")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    root = os.path.abspath(args.instance)

    cfg_path = os.path.join(root, fw.CONFIG_FILE)
    if not os.path.isfile(cfg_path):
        fw.die("no %s in %s — update is for a configured clone, not the base." % (fw.CONFIG_FILE, root))
    cfg = fw.load_config(cfg_path)
    ctx = fw.derive(cfg)
    try:
        manifest = fw.load_manifest(os.path.join(root, "ownership.json"))
    except fw.ConfigError as exc:
        fw.die(str(exc))

    try:
        rendered = fw.render_tree(os.path.join(root, "templates"), ctx, manifest)
    except fw.RenderError as exc:
        fw.die(str(exc))

    state = fw.load_state(root)
    if not state and not args.force:
        fw.warn("no/empty %s baseline: cannot tell framework changes from local edits, "
                "so changed framework files are written as *.rp-new instead of overwritten. "
                "Re-run after init, or pass --force to overwrite." % fw.STATE_FILE)
    created, updated, conflicts, unchanged, left = [], [], [], [], []

    for rel, fresh in sorted(rendered.items()):
        if manifest.classify(rel) not in ("framework", "conditional"):
            continue  # never touch project-owned files
        dst = os.path.join(root, rel)
        fresh_sha = fw.sha_text(fresh)
        baseline = state.get(rel)
        if not os.path.isfile(dst):
            created.append(rel)
            if not args.dry_run:
                fw.write_text(dst, fresh)
            state[rel] = fresh_sha
            continue
        on_disk_sha = fw.sha_text(fw.read_text(dst))
        if on_disk_sha == fresh_sha:
            unchanged.append(rel)
            state[rel] = fresh_sha
            continue
        framework_changed = baseline is None or fresh_sha != baseline
        user_edited = baseline is None or on_disk_sha != baseline
        if args.force:
            updated.append(rel)
            if not args.dry_run:
                fw.write_text(dst, fresh)
            state[rel] = fresh_sha
        elif baseline is not None and not framework_changed:
            # the framework did not change this file; never clobber a local edit
            left.append(rel)
        elif user_edited:
            # both sides changed, or no baseline to prove otherwise -> stay safe
            conflicts.append(rel)
            if not args.dry_run:
                fw.write_text(dst + ".rp-new", fresh)
            state[rel] = fresh_sha
        else:
            # framework changed, user did not edit -> refresh in place
            updated.append(rel)
            if not args.dry_run:
                fw.write_text(dst, fresh)
            state[rel] = fresh_sha

    # Previously-rendered framework/conditional outputs that are no longer active
    # (e.g. a subsystem was turned off). Computed from the state baseline, so it
    # works for any conditional glob, not just concrete file paths.
    active = set(rendered.keys())
    stale = [rel for rel in sorted(state)
             if rel not in active and os.path.isfile(os.path.join(root, rel))]

    if not args.dry_run:
        fw.save_state(root, state)

    fw.log("update: created=%d updated=%d unchanged=%d conflicts=%d left=%d%s"
           % (len(created), len(updated), len(unchanged), len(conflicts), len(left),
              " (dry-run)" if args.dry_run else ""))
    for rel in conflicts:
        fw.warn("  conflict: %s was edited locally; new version written to %s.rp-new" % (rel, rel))
    for rel in stale:
        fw.warn("  note: %s is now disabled by config but still on disk (left in place)" % rel)

    if not args.dry_run:
        import check_docs_consistency as guard
        rc = guard.main(["--instance", root])
        if rc != 0:
            fw.warn("Guard failed after update — review the changes above.")
            return rc
    if conflicts:
        fw.log("Review the .rp-new files, merge, then delete them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
