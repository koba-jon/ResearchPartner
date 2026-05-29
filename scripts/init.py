#!/usr/bin/env python3
"""Configure a ResearchPartner clone (one-time).

Renders the templates/ tree into a configured docs/ for this project, writes the
config, installs the git hook, and (optionally) makes a single commit. Designed
for the private-clone model: the user has already created their own private repo
and pointed origin at it (or passes --adopt-base-as-upstream to let init do the
origin->upstream rename). init NEVER pushes and NEVER creates a remote.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _framework as fw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------- #
# Interactive prompts
# --------------------------------------------------------------------------- #

def ask(prompt, default=""):
    suffix = " [%s]" % default if default else ""
    try:
        val = input("%s%s: " % (prompt, suffix)).strip()
    except EOFError:
        val = ""
    return val or default


def ask_choice(prompt, choices, default):
    while True:
        val = ask("%s (%s)" % (prompt, "/".join(choices)), default)
        if val in choices:
            return val
        fw.warn("  please choose one of: %s" % ", ".join(choices))


def ask_yesno(prompt, default="yes"):
    return ask_choice(prompt, ["yes", "no"], default)


# Guards so a stray multi-line paste (each pasted line answers the next prompt)
# cannot silently produce a garbage, committed instance. A rejected value
# re-prompts, consuming the bad line rather than accepting it.
_PASTE_RE = re.compile(r"[=(){};]|^#")


def ask_clean(prompt, default=""):
    """A short plain value (rejects code-like / oversized stray-paste lines)."""
    while True:
        v = ask(prompt, default)
        if len(v) <= 80 and not _PASTE_RE.search(v):
            return v
        fw.warn("  that looks like a stray paste; enter a short plain value.")


def ask_path(prompt):
    """Loop until a non-empty path is given; return it as an absolute path."""
    while True:
        v = ask(prompt)
        if v:
            return os.path.abspath(v)
        fw.warn("  please enter a path.")


def ask_confirm_or_edit(label, explanation, default, edit_fn, default_ok=None):
    """Offer a computed default; accept it (yes) or replace it (no -> edit_fn()).

    Prints a labelled, explained prompt, shows the proposed value, and asks yes/no.
    'yes' keeps the proposal; 'no' hands off to edit_fn() to gather a replacement.
    If default_ok rejects the proposal we skip the offer and go straight to edit_fn,
    so we never accept a value the edit path itself would reject.
    """
    print("\n%s" % label)
    print("  %s" % explanation)
    if default and (default_ok is None or default_ok(default)):
        if ask_yesno('  Use "%s"?' % default, "yes") == "yes":
            return default
    else:
        fw.warn("  no usable default detected; please enter a value.")
    return edit_fn()


def interview(root):
    cfg = dict(fw.DEFAULT_CONFIG)
    print("\nLet's configure your ResearchPartner clone.")
    print("  - Press Enter to accept the default shown in [brackets].")
    print("  - For a detected value, answer 'yes' to keep it or 'no' to type your own.")
    print("\n== Phase 1: where your project lives and where it runs ==")
    default_root = os.path.dirname(root)  # clone usually sits inside PROJECT_ROOT
    cfg["PROJECT_ROOT"] = ask_confirm_or_edit(
        "Project root",
        "The top-level folder of your workspace, where your code and data live "
        "(this clone usually sits inside it). Normally the folder shown below.",
        os.path.abspath(default_root),
        lambda: ask_path("  Enter the project root path to use instead"))
    cfg["FRAMEWORK_REPO_DIR"] = root
    cfg["CLAUDE_DIR"] = ask_confirm_or_edit(
        "Claude task-artifacts folder",
        "The folder where Claude Code saves its working files — task notes and "
        "intermediate outputs. A 'claude' sub-folder of the project root is usual.",
        os.path.abspath(os.path.join(cfg["PROJECT_ROOT"], "claude")),
        lambda: ask_path("  Enter the task-artifacts folder path to use instead"))

    print("\n  Compute environment: where you actually run experiments — this sets")
    print("  the path and runtime hints in your docs.")
    cfg["COMPUTE_ENV"] = ask_choice(
        "Compute environment", ["colab", "local-gpu", "local-cpu", "other"], "local-cpu")
    if cfg["COMPUTE_ENV"] == "colab":
        print("  Colab mounts your Google Drive; give the Drive path this project lives under.")
        cfg["COMPUTE_DRIVE"] = ask("Colab Drive root for this project",
                                   "/content/drive/MyDrive")

    print("\n== Phase 2: detect & ingest (read-only scan of your project) ==")
    scan = fw.scan_project(cfg["PROJECT_ROOT"], self_dir=root)
    print(scan["summary"])
    print(scan["tree"])
    cfg["INGEST_SUMMARY"] = scan["summary"]

    # Source mirror: auto-enabled when there is a PROJECT_ROOT/src to mirror. sync_src
    # mirrors that path specifically, so gating on has_code would mis-fire for code in
    # notebooks at the root or under lib/. No longer asked; set SRC_MIRROR_ENABLED=no
    # in config to keep your source out of this repo.
    cfg["SRC_MIRROR_ENABLED"] = "yes" if os.path.isdir(
        os.path.join(cfg["PROJECT_ROOT"], "src")) else "no"
    if cfg["SRC_MIRROR_ENABLED"] == "yes":
        print("\n  Found a src/ directory — your source will be mirrored (read-only) into")
        print("  this repo's src/ so the Claude Project can read it; refresh with `make sync-src`.")

    if not scan["has_code"]:
        print("\n== Phase 2b: intent interview (no code found — tell me the plan) ==")
        print("  No source code was detected, so a few words about the plan let your docs")
        print("  start from something real instead of placeholders.")
        cfg["INTENT_DOMAIN"] = ask("Research domain / field (e.g. NLP, genomics)")
        cfg["INTENT_STACK"] = ask("Main tools / stack (e.g. PyTorch, JAX, R)")
        cfg["INTENT_GOAL"] = ask("One-line goal of the project")
        cfg["INTENT_FIRST_STEP"] = ask("First concrete step you plan to take")

    print("\n== Phase 3: identity & languages ==")
    cfg["PROJECT_NAME"] = ask_confirm_or_edit(
        "Project name",
        "The display name used across your docs and the Claude project instructions.",
        os.path.basename(cfg["PROJECT_ROOT"]),
        lambda: ask_clean("  Enter the project name to use instead"),
        default_ok=lambda d: len(d) <= 80 and not _PASTE_RE.search(d))

    print("\n  Your name as it should appear in the docs (the human collaborator).")
    cfg["USER_NAME"] = ask_clean("Your name")

    print("\n  The next three languages can differ:")
    print("    - Chat: how Claude replies to you in conversation.")
    print("    - Docs: the language your generated docs are written in.")
    print("    - Code: the language for code comments and prompts.")
    cfg["CHAT_LANG"] = ask_clean("Chat reply language", "English")
    cfg["DOCS_LANG"] = ask_clean("Docs language", "English")
    cfg["CODE_LANG"] = ask_clean("Code / prompt language", "English")
    if fw.docs_lang_is_english(cfg["DOCS_LANG"]) == "no":
        print("\n  Note: the shipped docs are written in English. With DOCS_LANG=%s, your"
              % cfg["DOCS_LANG"])
        print("  Research Partner offers a one-time localization on the first session (a")
        print("  banner in docs/entrypoint.md); new docs are then authored in %s." % cfg["DOCS_LANG"])
    # The following are no longer asked; they take their DEFAULT_CONFIG values and can
    # be changed in config followed by `make update`:
    #   GENERATE_MANUAL ("yes")  - generate the GETTING_STARTED manual.
    #   ENABLE_AUTO_MODE ("yes") - include the Auto mode subsystem.
    #   EXPERIMENT_UNIT_LABEL ("Experiment") / ANALYSIS_RECORD_LABEL ("Note").
    #   SRC_MIRROR_ENABLED   - auto-set earlier from whether PROJECT_ROOT/src exists.
    return cfg


# --------------------------------------------------------------------------- #
# Render + write
# --------------------------------------------------------------------------- #

def render_all(root, cfg):
    ctx = fw.derive(cfg)
    # Free-text fields are DATA, not templates: neutralize any {{...}} inside them
    # so a goal line or scan summary that mentions a template var cannot abort the
    # render via the unresolved-token check.
    for _k in ("INTENT_DOMAIN", "INTENT_STACK", "INTENT_GOAL", "INTENT_FIRST_STEP", "INGEST_SUMMARY"):
        if isinstance(ctx.get(_k), str):
            ctx[_k] = ctx[_k].replace("{{", "{").replace("}}", "}")
    problems = fw.validate_config(cfg)
    if problems:
        fw.die("config is incomplete:\n  " + "\n  ".join(problems))
    manifest = fw.load_manifest(os.path.join(root, "ownership.json"))
    rendered = fw.render_tree(os.path.join(root, "templates"), ctx, manifest)
    return ctx, rendered


def write_rendered(root, rendered):
    for rel, content in sorted(rendered.items()):
        fw.write_text(os.path.join(root, rel), content)


# --------------------------------------------------------------------------- #
# Git lifecycle (strict boundaries)
# --------------------------------------------------------------------------- #

def _remotes(root):
    try:
        return set(fw.git("remote", cwd=root, check=False).split())
    except RuntimeError:
        return set()


def base_protection(root, force, adopt, git_ok=True, dry_run=False):
    if not fw.is_base_repo(root):
        return  # already a configured instance
    if force:
        fw.warn("--force: configuring in place despite the base marker.")
        return
    if adopt:
        if git_ok and fw.current_remote_url("origin", root) and "upstream" not in _remotes(root):
            if dry_run:
                fw.log("Dry run -- would rename remote origin -> upstream (skipped).")
            else:
                try:
                    fw.git("remote", "rename", "origin", "upstream", cwd=root)
                    fw.log("Renamed remote origin -> upstream.")
                except RuntimeError as exc:
                    fw.warn("could not rename origin -> upstream: %s" % exc)
        fw.log("Adopting base as upstream. Set your own private repo as origin before pushing.")
        return
    # Marker present without --force/--adopt: allow ONLY if this checkout has
    # already been detached from the base (an 'upstream' remote exists, per the
    # README flow). A pristine base has no 'upstream' -> refuse. With --skip-git
    # we cannot verify remotes, so we refuse (the marker check is never skipped).
    if git_ok and "upstream" in _remotes(root):
        return
    fw.die(
        "This looks like the ResearchPartner BASE repo (the .researchpartner-base "
        "marker is present and there is no 'upstream' remote). Configuring here would "
        "overwrite the base.\n"
        "  * Detach first: git remote rename origin upstream && git remote add origin <your-private-repo>, then re-run; or\n"
        "  * pass --adopt-base-as-upstream to let init do that rename; or\n"
        "  * pass --force if this is a downloaded copy (no git history) or you "
        "really mean to configure in place.")


def commit(root, project_name):
    try:
        fw.git("add", "-A", cwd=root)
        msg = ("Configure ResearchPartner instance for %s\n\n"
               "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" % project_name)
        fw.git("commit", "-m", msg, cwd=root)
        fw.log("Created one commit on the current branch (no push performed).")
    except RuntimeError as exc:
        fw.warn("commit skipped: %s" % exc)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv=None):
    p = argparse.ArgumentParser(description="Configure a ResearchPartner clone")
    p.add_argument("--config", help="JSON config to use (required with --non-interactive)")
    p.add_argument("--non-interactive", action="store_true", help="ask nothing; require --config")
    p.add_argument("--force", action="store_true", help="configure even over base marker / existing docs/")
    p.add_argument("--adopt-base-as-upstream", action="store_true",
                   help="rename origin->upstream and configure this checkout as your instance")
    p.add_argument("--skip-commit", action="store_true", help="render + configure but do not commit")
    p.add_argument("--skip-git", action="store_true", help="touch no git state at all (testing)")
    p.add_argument("--dry-run", action="store_true", help="show planned writes; write nothing")
    p.add_argument("--print-config", action="store_true", help="resolve + print config, then exit")
    args = p.parse_args(argv)
    root = ROOT

    # Safety gates run BEFORE building config, so a base / ZIP / live-instance user
    # is not put through the whole interview only to be refused at the end.
    # base_protection only fires on the unconfigured base; a configured clone passes
    # instantly. --print-config is allowed to inspect config without these gates.
    if not args.print_config:
        base_protection(root, args.force, args.adopt_base_as_upstream,
                        git_ok=not args.skip_git, dry_run=args.dry_run)
        docs_dir = os.path.join(root, "docs")
        if os.path.isdir(docs_dir) and os.listdir(docs_dir) and not (args.force or args.dry_run):
            fw.die("docs/ already exists and is non-empty — refusing to overwrite a live "
                   "instance. Pass --force to re-render.")

    # Build config
    if args.non_interactive or args.config:
        if not args.config:
            fw.die("--non-interactive requires --config <path>")
        cfg = fw.load_config(args.config)
        cfg.setdefault("FRAMEWORK_REPO_DIR", root)
        if not cfg.get("FRAMEWORK_REPO_DIR"):
            cfg["FRAMEWORK_REPO_DIR"] = root
        if not args.non_interactive:
            fw.log("Loaded config from %s" % args.config)
    else:
        cfg = interview(root)

    if args.print_config:
        import json
        print(json.dumps(fw.derive(cfg), indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    # Render (transactional: raises before any write if a token is unresolved)
    try:
        ctx, rendered = render_all(root, cfg)
    except (fw.RenderError, fw.ConfigError) as exc:
        fw.die(str(exc))

    if args.dry_run:
        manifest = fw.load_manifest(os.path.join(root, "ownership.json"))
        fw.log("Dry run — would write %d files:" % len(rendered))
        for rel in sorted(rendered):
            fw.log("  %s (%s)" % (rel, manifest.classify(rel)))
        return 0

    # Confirm (interactive only)
    if not (args.non_interactive or args.config):
        print("\n== Resolved config ==")
        for k in sorted(fw.DEFAULT_CONFIG):
            if k != "schema_version" and str(cfg.get(k, "")):
                print("  %s = %s" % (k, cfg[k]))
        if ask_yesno("\nProceed and write these files?", "yes") != "yes":
            fw.log("Aborted; nothing written.")
            return 0

    # Write outputs + config + render-baseline state (for update.py's rp-new safety)
    write_rendered(root, rendered)
    fw.save_config(cfg, os.path.join(root, fw.CONFIG_FILE))
    manifest = fw.load_manifest(os.path.join(root, "ownership.json"))
    state = {rel: fw.sha_text(content) for rel, content in rendered.items()
             if manifest.classify(rel) in ("framework", "conditional")}
    fw.save_state(root, state)
    fw.log("Wrote %d rendered files and %s." % (len(rendered), fw.CONFIG_FILE))

    # Convert from base -> configured instance
    marker = os.path.join(root, fw.MARKER_FILE)
    if os.path.isfile(marker):
        os.remove(marker)
        fw.log("Removed base marker (%s)." % fw.MARKER_FILE)

    # Optional src mirror
    if fw.truthy(cfg.get("SRC_MIRROR_ENABLED", "no")):
        import sync_src
        try:
            sync_src.main(["--instance", root])
        except SystemExit:
            pass

    # Install hook + run the guard
    if not args.skip_git and fw.is_git_repo(root):
        try:
            fw.git("config", "core.hooksPath", ".githooks", cwd=root)
            fw.log("Installed git hooks (core.hooksPath=.githooks).")
        except RuntimeError as exc:
            fw.warn("could not install hooks: %s" % exc)

    import check_docs_consistency as guard
    rc = guard.main(["--instance", root])
    if rc != 0:
        fw.warn("The freshly rendered docs did not pass the guard (template defect?). "
                "Files are left on disk for inspection.")

    # Commit
    if not args.skip_git and not args.skip_commit and fw.is_git_repo(root):
        commit(root, cfg.get("PROJECT_NAME", "project"))

    fw.log("\nResearchPartner configured. Next: review docs/entrypoint.md, paste "
           "project-instructions.txt into your Claude Project, and push to your "
           "private origin when ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
