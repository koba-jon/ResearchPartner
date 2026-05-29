#!/usr/bin/env python3
"""ResearchPartner docs consistency guard (clone mode).

A faithful Python port of the original Ruby guard, generalized for the
ResearchPartner template:

  * required-files / router lists match the (collapsed) ResearchPartner file
    set and are filtered through the ownership manifest, so a clone with a
    subsystem turned off is not flagged for an intentionally-absent file;
  * docs are language-agnostic (Unicode): there is no character/script policy,
    so Greek math letters and any non-Latin script are allowed;
  * the two byte-identical mirror checks and the section-reference logic are
    ported 1:1 from the Ruby oracle.

Run from a configured clone:  python3 scripts/check_docs_consistency.py
Check another instance:        python3 scripts/check_docs_consistency.py --instance /path
(usually invoked via `make docs-check` and the pre-commit hook.)
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _framework as fw  # noqa: E402

# Section-reference patterns (U+00A7 = the section sign). Same as the oracle.
PATH_SECTION_REF = re.compile(
    r"`?(docs/[A-Za-z0-9_/.-]+\.md)`?\s*§\s*"
    r"([0-9]+(?:\.[0-9]+)?(?:\s*-\s*[0-9]+(?:\.[0-9]+)?)?)"
)
LOCAL_SECTION_REF = re.compile(
    r"§\s*([0-9]+(?:\.[0-9]+)?(?:\s*-\s*[0-9]+(?:\.[0-9]+)?)?)"
)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+([0-9]+(?:\.[0-9]+)*)(?:\.|\s|$)")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

# Always-required files for a ResearchPartner clone (collapsed file set;
# GSAD's wave-branching.md and open-issues-and-future.md are intentionally
# dropped). Filtered through the manifest so conditional files don't appear.
REQUIRED_FILES = [
    "Makefile",
    ".githooks/pre-commit",
    "docs/entrypoint.md",
    "docs/operations/consistency-guard.md",
    "docs/operations/rules/README.md",
    "docs/operations/rules/operating-principles.md",
    "docs/operations/rules/forbidden-actions.md",
    "docs/operations/rules/operational-constraints.md",
    "docs/operations/rules/deliverable-checklist.md",
    "docs/operations/rules/update-rules.md",
    "docs/project/backlog/README.md",
    "docs/project/backlog/active-issues.md",
    "docs/project/backlog/layer-backlog.md",
    "docs/project/backlog/paper-readiness.md",
    "docs/project/backlog/dormant-hypotheses.md",
]

BACKLOG_ROUTES = [
    "active-issues.md", "layer-backlog.md", "paper-readiness.md",
    "dormant-hypotheses.md",
]
RULE_FILES = [
    "operating-principles.md", "forbidden-actions.md",
    "operational-constraints.md", "deliverable-checklist.md", "update-rules.md",
]
SHARED_ROUTES = ["docs/operations/rules/" + n for n in RULE_FILES]

# Backtick doc-path references (the templates cross-reference docs this way, not
# via markdown links, so the link check cannot see them).
BACKTICK_DOC_RE = re.compile(r"`(docs/[A-Za-z0-9_/.-]+\.md)`")


class Guard:
    def __init__(self, root, cfg, check_legacy_numbered=False):
        self.root = os.path.abspath(root)
        self.docs = os.path.join(self.root, "docs")
        self.cfg = cfg
        self.check_legacy = check_legacy_numbered
        self.errors = []
        self._section_cache = {}

    # -- helpers ----------------------------------------------------------- #
    def fail(self, msg):
        self.errors.append(msg)

    def _abs(self, rel):
        return os.path.join(self.root, rel)

    def _read(self, rel):
        return fw.read_text(self._abs(rel))

    def _rel(self, abspath):
        return os.path.relpath(abspath, self.root).replace(os.sep, "/")

    def _markdown_files(self):
        out = []
        for dirpath, dirnames, filenames in os.walk(self.docs):
            dirnames.sort()
            for name in sorted(filenames):
                if name.endswith(".md"):
                    out.append(os.path.join(dirpath, name))
        return out

    def _section_numbers(self, abspath):
        if abspath not in self._section_cache:
            nums = []
            if os.path.isfile(abspath):
                for line in fw.read_text(abspath).split("\n"):
                    m = HEADING_RE.match(line)
                    if m:
                        nums.append(m.group(1))
            self._section_cache[abspath] = nums
        return self._section_cache[abspath]

    @staticmethod
    def _extract_fenced_block(text, heading, lang):
        idx = text.find(heading)
        if idx < 0:
            return None
        rest = text[idx:]
        m = re.search(r"```%s\n(.*?)\n```" % re.escape(lang), rest, re.S)
        return m.group(1).strip() if m else None

    def _check_section_reference(self, source_rel, target_abs, target_label, raw):
        if not os.path.isfile(target_abs):
            self.fail("%s: section reference target does not exist: %s §%s"
                      % (source_rel, target_label, raw))
            return
        available = self._section_numbers(target_abs)
        for sec in [s.strip() for s in re.split(r"\s*-\s*", raw) if s.strip()]:
            if sec not in available:
                self.fail("%s: missing section heading %s §%s"
                          % (source_rel, target_label, sec))

    # -- check groups ------------------------------------------------------ #
    def check_required_files(self):
        required = self.cfg["_manifest"].required_docs(self.cfg, REQUIRED_FILES) \
            if "_manifest" in self.cfg else REQUIRED_FILES
        for rel in required:
            if not os.path.isfile(self._abs(rel)):
                self.fail("missing required file: %s" % rel)

    def check_makefile_and_hook(self):
        mk_path = self._abs("Makefile")
        if os.path.isfile(mk_path):
            mk = fw.read_text(mk_path)
            if not re.search(r"^docs-check:", mk, re.M):
                self.fail("Makefile is missing docs-check target")
            if not re.search(r"^install-hooks:", mk, re.M):
                self.fail("Makefile is missing install-hooks target")
        hook_path = self._abs(".githooks/pre-commit")
        if os.path.isfile(hook_path):
            if not os.access(hook_path, os.X_OK):
                self.fail(".githooks/pre-commit is not executable")
            if fw.GUARD_SCRIPT not in fw.read_text(hook_path):
                self.fail(".githooks/pre-commit does not run docs consistency script")

    def check_per_file(self):
        for abspath in self._markdown_files():
            rel = self._rel(abspath)
            text = fw.read_text(abspath)

            # 1. markdown links resolve
            for raw_target in LINK_RE.findall(text):
                target = raw_target.split("#", 1)[0].strip()
                if not target:
                    continue
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1]
                else:
                    # drop an optional markdown link title:  path "title" / path 'title'
                    target = re.split(r"""\s+["']""", target, 1)[0]
                resolved = os.path.normpath(os.path.join(os.path.dirname(abspath), target))
                if not os.path.exists(resolved):
                    self.fail("%s: missing markdown link target %s" % (rel, raw_target))

            # 1b. backtick doc-path references must resolve on disk
            for ref in BACKTICK_DOC_RE.findall(text):
                if not os.path.isfile(self._abs(ref)):
                    self.fail("%s: backtick reference to missing doc `%s`" % (rel, ref))

            # NOTE: docs are language-agnostic (Unicode). There is intentionally
            # no character/script policy here -- Greek math letters and any
            # non-Latin script are valid docs content.

            # 2. forbidden / legacy paths
            if re.search(r"docs/docs/", text):
                self.fail("%s: contains duplicated docs path" % rel)
            if self.check_legacy:
                legacy = {
                    r"00_INDEX\.md": "legacy startup filename",
                    r"docs/[0-9]{2}_[A-Z0-9_]+\.md": "legacy numbered root docs path",
                    r"(?<![A-Za-z0-9_])[0-9]{2}_[A-Z0-9_]+\.md": "legacy numbered filename",
                }
                for pat, label in legacy.items():
                    if re.search(pat, text):
                        self.fail("%s: contains %s" % (rel, label))

            # 3. section references (cross-file then local, skipping overlaps)
            path_ranges = []
            for m in PATH_SECTION_REF.finditer(text):
                path_ranges.append((m.start(), m.end()))
                target_label = m.group(1)
                self._check_section_reference(
                    rel, os.path.normpath(self._abs(target_label)), target_label, m.group(2))
            for m in LOCAL_SECTION_REF.finditer(text):
                off = m.start()
                if any(a <= off < b for a, b in path_ranges):
                    continue
                self._check_section_reference(rel, abspath, rel, m.group(1))

    def check_mirror_blocks(self):
        try:
            entrypoint = self._read("docs/entrypoint.md")
            memory = self._read("docs/operations/project-memory-and-instructions.md")
            prompt_factory = self._read("docs/operations/prompt-factory.md")
        except FileNotFoundError as exc:
            self.fail("mirror check could not read a file: %s" % exc)
            return

        ep_instr = self._extract_fenced_block(
            entrypoint, "### Canonical Project Instructions Mirror", "text")
        mem_instr = self._extract_fenced_block(
            memory, "## 2. Current Instructions Candidate", "text")
        if ep_instr is None or mem_instr is None:
            self.fail("could not extract Project Instructions mirror blocks")
        elif ep_instr != mem_instr:
            self.fail("Project Instructions mirror drift: entrypoint.md differs "
                      "from project-memory-and-instructions.md")

        ep_hdr = self._extract_fenced_block(entrypoint, "Canonical prompt header:", "bash")
        pf_hdr = self._extract_fenced_block(prompt_factory, "## 2. Canonical Header", "bash")
        if ep_hdr is None or pf_hdr is None:
            self.fail("could not extract canonical prompt headers")
        elif ep_hdr != pf_hdr:
            self.fail("canonical prompt header drift: entrypoint and prompt-factory differ")

    def check_maintenance_n(self):
        path = self._abs("docs/operations/maintenance-mode.md")
        if not os.path.isfile(path):
            return  # optional subsystem
        mnt = fw.read_text(path)
        m = re.search(r"Last updated: .*?N=(\d+)", mnt)
        log_ns = [int(x) for x in re.findall(r"^\| (\d+) \| \d{4}-\d{2}-\d{2} \|", mnt, re.M)]
        if m and log_ns and int(m.group(1)) != max(log_ns):
            self.fail("Maintenance Mode Last updated N=%s does not match activation log max N=%d"
                      % (m.group(1), max(log_ns)))

    def check_routers(self):
        backlog = self._abs("docs/project/backlog/README.md")
        if os.path.isfile(backlog):
            text = fw.read_text(backlog)
            for name in BACKLOG_ROUTES:
                if name not in text:
                    self.fail("backlog README does not route to %s" % name)
        rules = self._abs("docs/operations/rules/README.md")
        if os.path.isfile(rules):
            text = fw.read_text(rules)
            for name in RULE_FILES:
                if name not in text:
                    self.fail("rules README does not route to %s" % name)
        shared = self._abs("docs/operations/shared-instructions.md")
        if os.path.isfile(shared):
            text = fw.read_text(shared)
            for path in SHARED_ROUTES:
                if path not in text:
                    self.fail("shared-instructions router does not route to %s" % path)

    def run(self):
        if not os.path.isdir(self.docs):
            self.fail("no docs/ directory found at %s (is this a configured clone?)"
                      % self.root)
            return self.errors
        self.check_required_files()
        self.check_makefile_and_hook()
        self.check_per_file()
        self.check_mirror_blocks()
        self.check_maintenance_n()
        self.check_routers()
        return self.errors


def _load_instance_config(root):
    """Read the instance's config; fall back to a strict safe profile."""
    cfg_path = os.path.join(root, fw.CONFIG_FILE)
    if os.path.isfile(cfg_path):
        try:
            cfg = fw.derive(fw.load_config(cfg_path))
        except fw.ConfigError:
            cfg = fw.derive(dict(fw.DEFAULT_CONFIG))
    else:
        cfg = fw.derive(dict(fw.DEFAULT_CONFIG))
    man_path = os.path.join(root, "ownership.json")
    if os.path.isfile(man_path):
        try:
            cfg["_manifest"] = fw.load_manifest(man_path)
        except fw.ConfigError as exc:
            fw.die(str(exc))
    return cfg


def main(argv=None):
    parser = argparse.ArgumentParser(description="ResearchPartner docs consistency guard")
    parser.add_argument("--instance", default=".", help="path to the clone to check")
    parser.add_argument("--check-legacy-numbered", action="store_true",
                        help="also flag GSAD-style numbered/00_INDEX filenames")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.instance)
    cfg = _load_instance_config(root)
    legacy = args.check_legacy_numbered or fw.truthy(cfg.get("CHECK_LEGACY_NUMBERED", ""))
    guard = Guard(root, cfg, check_legacy_numbered=legacy)
    errors = guard.run()

    if not errors:
        print("Docs consistency OK")
        return 0
    sys.stderr.write("Docs consistency FAILED\n")
    for err in errors:
        sys.stderr.write("- %s\n" % err)
    return 1


if __name__ == "__main__":
    sys.exit(main())
