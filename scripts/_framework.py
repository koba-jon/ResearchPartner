#!/usr/bin/env python3
"""ResearchPartner base-template shared library.

Zero third-party dependencies (Python stdlib only). This module is imported by
init.py, update.py, sync_src.py and check_docs_consistency.py. It provides:

  * the template engine ({{TOKEN}} substitution + line/inline conditionals +
    <!-- include: --> fragments, with transactional whole-tree rendering),
  * the config layer (defaults, load/save/validate, derived tokens),
  * the ownership Manifest (framework / project / conditional / ignore),
  * thin git wrappers (never push, never create remotes),
  * a bounded read-only project ingest scan,
  * base-side lint helpers (templates + manifest + token sanity).

Design notes live in docs/operations/consistency-guard.md of a rendered clone.
"""

import hashlib
import json
import os
import re
import subprocess
import sys

if sys.version_info < (3, 8):  # pragma: no cover - environment guard
    sys.stderr.write("ResearchPartner requires Python 3.8 or newer.\n")
    sys.exit(2)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

INIT_VERSION = 1
SCHEMA_VERSION = 1
GUARD_SCRIPT = "scripts/check_docs_consistency.py"
MARKER_FILE = ".researchpartner-base"
CONFIG_FILE = "researchpartner.config.json"
STATE_FILE = ".researchpartner-state.json"
ROLE_TERM = "Research Partner"

# {{UPPER_SNAKE}} with optional inner whitespace. Disjoint from shell ${VAR}.
TOKEN_RE = re.compile(r"\{\{\s*([A-Z][A-Z0-9_]*)\s*\}\}")

# Conditional markers (HTML comments so they are invisible in raw Markdown).
# The condition capture forbids '>' so a marker can never swallow its own
# closing '-->' (which would let a whole-line inline conditional be misread as
# an unclosed block-if).
_IF_LINE = re.compile(r"^<!--\s*if:\s*([^>]+?)\s*-->$")
_ELSE_LINE = re.compile(r"^<!--\s*else\s*-->$")
_ENDIF_LINE = re.compile(r"^<!--\s*endif\s*-->$")
_INCLUDE_LINE = re.compile(r"^<!--\s*include:\s*([^>]+?)\s*-->$")
_INLINE_COND = re.compile(
    r"<!--\s*if:\s*([^>]+?)\s*-->(.*?)"
    r"(?:<!--\s*else\s*-->(.*?))?"
    r"<!--\s*endif\s*-->"
)

_TRUTHY = {"yes", "true", "1", "on"}

# Docs-language names treated as English (the skeleton ships in English, so they
# need no localization). Anything else triggers the one-time localization offer.
_ENGLISH_DOCS_LANGS = {"english", "en", "en-us", "en-gb", "en_us", "en_gb", ""}


class RenderError(Exception):
    """Raised when a template cannot be rendered safely."""


class ConfigError(Exception):
    """Raised when a config file is missing keys or malformed."""


# --------------------------------------------------------------------------- #
# Small IO helpers
# --------------------------------------------------------------------------- #

def log(msg):
    print(msg)


def warn(msg):
    sys.stderr.write(msg + "\n")


def die(msg, code=1):
    warn("error: " + msg)
    sys.exit(code)


def read_text(path):
    """Read a file as UTF-8 and normalise CRLF -> LF (byte-mirror safety)."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n").replace("\r", "\n")


def write_text(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def truthy(value):
    return str(value).strip().lower() in _TRUTHY


def sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state(root):
    """Render-baseline hashes for framework files (used by update.py)."""
    path = os.path.join(root, STATE_FILE)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except ValueError:
            return {}
    return {}


def save_state(root, state):
    with open(os.path.join(root, STATE_FILE), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")


# --------------------------------------------------------------------------- #
# Template engine
# --------------------------------------------------------------------------- #

def _eval_cond(expr, ctx):
    """Evaluate a conditional expression: ``VAR=value`` or boolean ``VAR``."""
    if "=" in expr:
        var, _, value = expr.partition("=")
        return str(ctx.get(var.strip(), "")) == value.strip()
    return truthy(ctx.get(expr.strip(), ""))


def expand_includes(text, resolver, _seen=None, _depth=0):
    """Splice ``<!-- include: path -->`` lines with the referenced fragment.

    ``resolver(path)`` returns the raw fragment text. Includes may nest up to a
    small bounded depth; a cycle or an over-deep include raises RenderError.
    """
    if _depth > 10:
        raise RenderError("include nesting too deep (possible cycle)")
    _seen = _seen or []
    out = []
    for line in text.split("\n"):
        m = _INCLUDE_LINE.match(line.strip())
        if not m:
            out.append(line)
            continue
        path = m.group(1)
        if ".." in path.split("/") or path.startswith("/"):
            raise RenderError("include path must stay within templates/: %s" % path)
        if path in _seen:
            raise RenderError("include cycle detected at %s" % path)
        fragment = resolver(path)
        if fragment is None:
            raise RenderError("include target not found: %s" % path)
        expanded = expand_includes(fragment, resolver, _seen + [path], _depth + 1)
        out.append(expanded.rstrip("\n"))
    return "\n".join(out)


def apply_conditionals(text, ctx):
    """Resolve block (whole-line) and inline conditionals.

    Block markers sit alone on their own line and gate the lines between them.
    Inline markers wrap a span inside one line. Nesting of block markers is
    supported via a stack; if an inline conditional empties an originally
    non-empty line, that line is dropped (so conditional table rows vanish
    cleanly instead of leaving a blank row).
    """
    out = []
    # stack of dicts: cond (bool), parent_emit (bool), else_seen (bool)
    stack = []

    def emitting():
        if not stack:
            return True
        top = stack[-1]
        own = (not top["cond"]) if top["else_seen"] else top["cond"]
        return top["parent"] and own

    for line in text.split("\n"):
        s = line.strip()

        m_if = _IF_LINE.match(s)
        if m_if:
            stack.append({
                "cond": _eval_cond(m_if.group(1), ctx),
                "parent": emitting(),
                "else_seen": False,
            })
            continue
        if _ELSE_LINE.match(s):
            if not stack:
                raise RenderError("<!-- else --> without matching if")
            stack[-1]["else_seen"] = True
            continue
        if _ENDIF_LINE.match(s):
            if not stack:
                raise RenderError("<!-- endif --> without matching if")
            stack.pop()
            continue

        if not emitting():
            continue

        rendered = _render_inline(line, ctx)
        if s != "" and rendered.strip() == "":
            # An inline conditional removed the entire line's content.
            continue
        out.append(rendered)

    if stack:
        raise RenderError("unclosed <!-- if --> block")
    return "\n".join(out)


def _render_inline(line, ctx):
    def repl(m):
        cond, body, elsebody = m.group(1), m.group(2), m.group(3)
        if _eval_cond(cond, ctx):
            return body
        return elsebody or ""
    return _INLINE_COND.sub(repl, line)


def substitute_tokens(text, ctx):
    def repl(m):
        name = m.group(1)
        if name in ctx:
            return str(ctx[name])
        return m.group(0)  # leave unknown tokens for find_unresolved
    return TOKEN_RE.sub(repl, text)


def render_str(text, ctx, resolver=None):
    """Full render of one template string: includes -> conditionals -> tokens."""
    if resolver is not None:
        text = expand_includes(text, resolver)
    text = apply_conditionals(text, ctx)
    text = substitute_tokens(text, ctx)
    return text


def find_unresolved(text):
    """Return [(lineno, token)] for any surviving {{TOKEN}} after a render."""
    found = []
    for i, line in enumerate(text.split("\n"), start=1):
        for m in TOKEN_RE.finditer(line):
            found.append((i, m.group(1)))
    return found


def template_to_output(rel):
    """Map a templates/-relative path to its rendered output path (or None).

    ``_fragments/`` are include-only partials and never produced as output.
    """
    rel = rel.replace(os.sep, "/")
    if rel.startswith("_fragments/"):
        return None
    if rel == "project-instructions.template.txt":
        return "project-instructions.txt"
    if rel == "README.clone.md.tmpl":
        return "README.md"
    if rel.endswith(".tmpl"):
        return rel[: -len(".tmpl")]
    return rel


def iter_template_files(templates_dir):
    """Yield templates/-relative paths of all render-source files."""
    for dirpath, dirnames, filenames in os.walk(templates_dir):
        dirnames.sort()
        for name in sorted(filenames):
            if name == ".DS_Store":
                continue
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, templates_dir).replace(os.sep, "/")


def render_tree(templates_dir, ctx, manifest):
    """Render every active template into an in-memory {output_rel: content}.

    Transactional: if any output still contains an unresolved {{TOKEN}}, raise
    before the caller writes anything to disk.
    """
    def resolver(path):
        frag_path = os.path.join(templates_dir, path)
        if not os.path.isfile(frag_path):
            return None
        return read_text(frag_path)

    rendered = {}
    problems = []
    for rel in iter_template_files(templates_dir):
        out_rel = template_to_output(rel)
        if out_rel is None:
            continue  # fragment / partial
        if not manifest.is_active(out_rel, ctx):
            continue  # conditional file turned off
        raw = read_text(os.path.join(templates_dir, rel))
        content = render_str(raw, ctx, resolver)
        for lineno, token in find_unresolved(content):
            problems.append("%s:%d unresolved token {{%s}}" % (out_rel, lineno, token))
        rendered[out_rel] = content

    if problems:
        raise RenderError(
            "render produced unresolved tokens (nothing written):\n  "
            + "\n  ".join(problems)
        )
    return rendered


# --------------------------------------------------------------------------- #
# Config layer
# --------------------------------------------------------------------------- #

# Required keys a config must supply (everything else has a default).
REQUIRED_KEYS = [
    "PROJECT_NAME", "USER_NAME", "CHAT_LANG", "DOCS_LANG", "CODE_LANG",
    "PROJECT_ROOT", "FRAMEWORK_REPO_DIR", "CLAUDE_DIR", "COMPUTE_ENV",
    "SRC_MIRROR_ENABLED", "ENABLE_AUTO_MODE", "GENERATE_MANUAL",
]

DEFAULT_CONFIG = {
    "schema_version": SCHEMA_VERSION,
    "PROJECT_NAME": "",
    "USER_NAME": "",
    "CHAT_LANG": "English",
    "DOCS_LANG": "English",
    "CODE_LANG": "English",
    "PROJECT_ROOT": "",
    "FRAMEWORK_REPO_DIR": "",
    "CLAUDE_DIR": "",
    "COMPUTE_ENV": "local-cpu",        # colab | local-gpu | local-cpu | other
    "COMPUTE_DRIVE": "",
    "SRC_MIRROR_ENABLED": "no",
    "ENABLE_AUTO_MODE": "yes",         # Auto mode subsystem on by default (init no longer asks)
    "GENERATE_MANUAL": "yes",
    "ENABLE_PUBLISH_STEP": "yes",      # on by default: prompt-factory ends prompts with a Publish (commit+push docs repo) AFTER the task's Verification; set "no" to keep commit/push manual
    "EXPERIMENT_UNIT_LABEL": "Experiment",
    "ANALYSIS_RECORD_LABEL": "Note",
    # Optional shell-var-name overrides; blank -> derived from PROJECT_NAME
    # (e.g. a project migrating in can keep its established variable names).
    "PROJECT_VAR": "",
    "REPO_VAR": "",
    "COMPUTE_DRIVE_VAR": "",
    "INTENT_DOMAIN": "",
    "INTENT_STACK": "",
    "INTENT_GOAL": "",
    "INTENT_FIRST_STEP": "",
    "INGEST_SUMMARY": "",
}

_COMPUTE_ENVS = {"colab", "local-gpu", "local-cpu", "other"}
_YESNO = {"yes", "no"}


def shell_ident(name):
    """Turn an arbitrary project name into a SHELL-SAFE uppercase identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if not cleaned:
        # All-non-ASCII name (e.g. Japanese): fall back to a stable, distinct
        # shell-safe stem so two different names do not collide on a fixed "PROJECT".
        cleaned = "PROJECT_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:6].upper()
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def docs_lang_is_english(docs_lang):
    """Whether DOCS_LANG is English ('yes'/'no'); non-English triggers the
    one-time docs localization offer (the skeleton always ships in English)."""
    return "yes" if str(docs_lang).strip().lower() in _ENGLISH_DOCS_LANGS else "no"


def load_config(path):
    if not os.path.isfile(path):
        raise ConfigError("config file not found: %s" % path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as exc:
        raise ConfigError("config file is not valid JSON: %s" % exc)
    if not isinstance(data, dict):
        raise ConfigError("config file must be a JSON object")
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in data.items() if not k.startswith("_")})
    return merged


def save_config(cfg, path):
    public = {k: v for k, v in cfg.items() if not k.startswith("_")}
    public.setdefault("schema_version", SCHEMA_VERSION)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(public, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def validate_config(cfg):
    """Return a list of human-readable problems ([] means valid)."""
    problems = []
    for key in REQUIRED_KEYS:
        if not str(cfg.get(key, "")).strip():
            problems.append("missing required value: %s" % key)
    env = cfg.get("COMPUTE_ENV", "")
    if env and env not in _COMPUTE_ENVS:
        problems.append("COMPUTE_ENV must be one of %s" % sorted(_COMPUTE_ENVS))
    for key in ("SRC_MIRROR_ENABLED", "ENABLE_AUTO_MODE", "GENERATE_MANUAL",
                "ENABLE_PUBLISH_STEP"):
        val = str(cfg.get(key, "")).strip().lower()
        if val and val not in _YESNO:
            problems.append("%s must be 'yes' or 'no'" % key)
    if env == "colab" and not str(cfg.get("COMPUTE_DRIVE", "")).strip():
        problems.append("COMPUTE_DRIVE is required when COMPUTE_ENV=colab")
    ident = re.compile(r"^[A-Z_][A-Z0-9_]*$")
    for key in ("PROJECT_VAR", "REPO_VAR", "COMPUTE_DRIVE_VAR"):
        v = str(cfg.get(key, "")).strip()
        if v and not ident.match(v):
            problems.append("%s must be a shell-safe identifier (UPPER_SNAKE) if set" % key)
    return problems


def derive(cfg):
    """Return cfg augmented with derived tokens. Pure; no I/O."""
    ctx = dict(cfg)
    name = cfg.get("PROJECT_NAME", "") or "PROJECT"
    stem = shell_ident(name)
    ctx["ROLE_TERM"] = ROLE_TERM
    # Respect an explicit override (so a migrating project keeps its var names),
    # otherwise derive a shell-safe name from PROJECT_NAME.
    ctx["PROJECT_VAR"] = (cfg.get("PROJECT_VAR") or "").strip() or (stem + "_ROOT")
    ctx["REPO_VAR"] = (cfg.get("REPO_VAR") or "").strip() or (stem + "_DOCS")
    ctx["COMPUTE_DRIVE_VAR"] = (cfg.get("COMPUTE_DRIVE_VAR") or "").strip() or (stem + "_DRIVE")
    # Brace-form helpers so templates can write {{REPO_VAR_BRACE}}/src -> ${X_DOCS}/src
    ctx["PROJECT_VAR_BRACE"] = "${" + ctx["PROJECT_VAR"] + "}"
    ctx["REPO_VAR_BRACE"] = "${" + ctx["REPO_VAR"] + "}"
    ctx["COMPUTE_DRIVE_VAR_BRACE"] = "${" + ctx["COMPUTE_DRIVE_VAR"] + "}"
    ctx["DOCS_LANG_IS_ENGLISH"] = docs_lang_is_english(ctx.get("DOCS_LANG", ""))
    return ctx


# --------------------------------------------------------------------------- #
# Ownership manifest
# --------------------------------------------------------------------------- #

def _glob_match(glob, path):
    """Match a path against a glob where '**' spans directories and '*' one
    segment. Returns True/False. Pure, stdlib-only (fnmatch lacks '**')."""
    g = glob.split("/")
    p = path.split("/")

    def rec(gi, pi):
        if gi == len(g):
            return pi == len(p)
        token = g[gi]
        if token == "**":
            # ** matches zero or more segments
            for skip in range(0, len(p) - pi + 1):
                if rec(gi + 1, pi + skip):
                    return True
            return False
        if pi == len(p):
            return False
        if _seg_match(token, p[pi]):
            return rec(gi + 1, pi + 1)
        return False

    return rec(0, 0)


def _seg_match(token, segment):
    # Translate a single-segment glob ('*' and '?') to a regex.
    rx = ["^"]
    for ch in token:
        if ch == "*":
            rx.append("[^/]*")
        elif ch == "?":
            rx.append("[^/]")
        else:
            rx.append(re.escape(ch))
    rx.append("$")
    return re.match("".join(rx), segment) is not None


class Manifest:
    def __init__(self, rules):
        # Each rule: {"glob": str, "owner": str, "when": {VAR: value} optional}
        self.rules = rules

    def _match(self, rel):
        """Return the most specific matching rule (longest glob), or None."""
        best = None
        best_specificity = -1
        for rule in self.rules:
            if _glob_match(rule["glob"], rel):
                # Specificity: non-** segment count, tie-broken by glob length.
                segs = [s for s in rule["glob"].split("/") if s != "**"]
                score = len(segs) * 1000 + len(rule["glob"])
                if score > best_specificity:
                    best_specificity = score
                    best = rule
        return best

    def classify(self, rel):
        rule = self._match(rel)
        return rule["owner"] if rule else "project"

    def is_active(self, rel, cfg):
        """True if this output path should exist for the given config."""
        rule = self._match(rel)
        if rule is None:
            return True
        if rule["owner"] == "ignore":
            return False
        when = rule.get("when")
        if when:
            return all(str(cfg.get(k, "")) == str(v) for k, v in when.items())
        return True

    def framework_paths(self, cfg, templates_dir):
        """Active output paths classified framework or active-conditional."""
        paths = []
        for rel in iter_template_files(templates_dir):
            out = template_to_output(rel)
            if out is None:
                continue
            if not self.is_active(out, cfg):
                continue
            if self.classify(out) in ("framework", "conditional"):
                paths.append(out)
        return sorted(paths)

    def required_docs(self, cfg, base_required):
        """Filter a static required-file list down to active paths."""
        return [p for p in base_required if self.is_active(p, cfg)]


def load_manifest(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ConfigError("ownership manifest %s is unreadable or not valid JSON: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ConfigError("ownership manifest %s must be a JSON object with a 'rules' list" % path)
    return Manifest(data["rules"])


# --------------------------------------------------------------------------- #
# Git wrappers (intentionally minimal; NEVER push / create remotes)
# --------------------------------------------------------------------------- #

def git(*args, cwd=".", check=True):
    proc = subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout.strip()


def is_git_repo(root):
    try:
        return git("rev-parse", "--is-inside-work-tree", cwd=root) == "true"
    except RuntimeError:
        return False


def current_remote_url(name, cwd="."):
    try:
        return git("remote", "get-url", name, cwd=cwd, check=False) or None
    except RuntimeError:
        return None


def is_base_repo(root):
    return os.path.isfile(os.path.join(root, MARKER_FILE))


# --------------------------------------------------------------------------- #
# Read-only project ingest scan
# --------------------------------------------------------------------------- #

class ScanCaps:
    max_files = 80
    max_depth = 3
    max_tree_lines = 60


_SCAN_DENYLIST = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".env",
    ".mypy_cache", ".pytest_cache", ".ipynb_checkpoints", ".idea", ".vscode",
    "datasets", "data", "checkpoints", "wandb", "dist", "build",
}


def _is_denied(name):
    if name in _SCAN_DENYLIST:
        return True
    if name.startswith("checkpoints") or name.startswith("test_result"):
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def scan_project(root, self_dir=None, caps=ScanCaps):
    """Bounded, read-only walk of ``root``. Records names only (no contents).

    Returns a dict with: summary (str), tree (str), and signal booleans/counts.
    Prunes denylisted and deep directories before descending.
    """
    root = os.path.abspath(root)
    self_dir = os.path.abspath(self_dir) if self_dir else None
    files = []
    tree_lines = []
    counts = {"py": 0, "ipynb": 0}
    signals = {"has_src": False, "has_claude": False, "has_reqs": False}

    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if depth >= caps.max_depth:
            dirnames[:] = []
        # prune in place so we never descend into heavy/irrelevant dirs
        dirnames[:] = sorted(
            d for d in dirnames
            if not _is_denied(d)
            and not (self_dir and os.path.abspath(os.path.join(dirpath, d)) == self_dir)
        )
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""
        base = os.path.basename(dirpath)
        if base in ("src", "lib", "app"):
            signals["has_src"] = True
        if base == "claude":
            signals["has_claude"] = True
        if len(tree_lines) < caps.max_tree_lines:
            indent = "  " * depth
            tree_lines.append("%s%s/" % (indent, base if rel_dir else os.path.basename(root)))
        for name in sorted(filenames):
            if name == ".DS_Store":
                continue
            if name in ("requirements.txt", "pyproject.toml", "environment.yml"):
                signals["has_reqs"] = True
            if name.endswith(".py"):
                counts["py"] += 1
            elif name.endswith(".ipynb"):
                counts["ipynb"] += 1
            if len(files) < caps.max_files:
                rel = os.path.join(rel_dir, name) if rel_dir else name
                files.append(rel)
                if len(tree_lines) < caps.max_tree_lines:
                    tree_lines.append("%s  %s" % ("  " * depth, name))

    truncated = counts["py"] + counts["ipynb"] > len(files)
    tree = "\n".join(tree_lines)
    if len(tree_lines) >= caps.max_tree_lines:
        tree += "\n  ... (truncated)"

    bits = []
    if counts["py"]:
        bits.append("%d Python module(s)" % counts["py"])
    if counts["ipynb"]:
        bits.append("%d notebook(s)" % counts["ipynb"])
    if signals["has_src"]:
        bits.append("a source directory")
    if signals["has_reqs"]:
        bits.append("a dependency manifest")
    if signals["has_claude"]:
        bits.append("an existing claude/ artifacts directory")
    summary = ("Detected " + ", ".join(bits) + ".") if bits else \
        "No source code detected at the project root."

    return {
        "summary": summary,
        "tree": tree,
        "counts": counts,
        "signals": signals,
        "has_code": bool(counts["py"] or counts["ipynb"] or signals["has_src"]),
        "truncated": truncated,
    }


# --------------------------------------------------------------------------- #
# Base-side lint (templates + manifest + token sanity)
# --------------------------------------------------------------------------- #

def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def known_token_names():
    names = set(DEFAULT_CONFIG.keys())
    names.discard("schema_version")
    names.update({
        "ROLE_TERM", "PROJECT_VAR", "REPO_VAR", "COMPUTE_DRIVE_VAR",
        "PROJECT_VAR_BRACE", "REPO_VAR_BRACE", "COMPUTE_DRIVE_VAR_BRACE",
        "DOCS_LANG_IS_ENGLISH",
    })
    return names


def lint_templates(root=None):
    """Assert every {{TOKEN}} in templates/ is a known config or derived key,
    and that the two mirror fragments are referenced. Returns list of problems."""
    root = root or _repo_root()
    templates_dir = os.path.join(root, "templates")
    problems = []
    known = known_token_names()
    if not os.path.isdir(templates_dir):
        return ["templates/ directory not found"]
    # A default context so we can attempt a real render (catches unbalanced or
    # mixed-form conditionals, which token-scanning alone would miss).
    probe = derive(dict(DEFAULT_CONFIG, PROJECT_NAME="Probe", USER_NAME="Probe",
                        PROJECT_ROOT="/probe", FRAMEWORK_REPO_DIR="/probe/repo",
                        CLAUDE_DIR="/probe/claude"))

    def resolver(path):
        fp = os.path.join(templates_dir, path)
        return read_text(fp) if os.path.isfile(fp) else None

    # Single-brace shell-style refs to a token name (e.g. ${PROJECT_VAR_BRACE})
    # never expand -- tokens render only via {{...}} -- so they leak the literal
    # name into output. ${CLAUDE_DIR} is a real prompt shell var (not a token), exempt.
    leak_names = sorted((n for n in known if n != "CLAUDE_DIR"), key=len, reverse=True)
    leak_re = re.compile(r"\$\{(" + "|".join(re.escape(n) for n in leak_names) + r")\}")

    for rel in iter_template_files(templates_dir):
        text = read_text(os.path.join(templates_dir, rel))
        for lineno, token in find_unresolved(text):
            if token not in known:
                problems.append("templates/%s:%d unknown token {{%s}}" % (rel, lineno, token))
        for m in leak_re.finditer(text):
            lineno = text.count("\n", 0, m.start()) + 1
            problems.append("templates/%s:%d single-brace token leak ${%s} "
                            "(use {{%s}} or a {{..._BRACE}} token; tokens expand only via {{...}})"
                            % (rel, lineno, m.group(1), m.group(1)))
        try:
            out = render_str(text, probe, resolver)
        except RenderError as exc:
            problems.append("templates/%s: %s" % (rel, exc))
        else:
            for i, line in enumerate(out.split("\n"), 1):
                if re.search(r"<!--\s*(?:if:|else\s*-->|endif\s*-->|include:)", line):
                    problems.append(
                        "templates/%s:%d leftover conditional/include marker "
                        "(a marker must be alone on its line OR a complete inline "
                        "if...endif on one line): %s" % (rel, i, line.strip()[:70]))
    # fragments must exist
    for frag in ("_fragments/project-instructions.txt", "_fragments/canonical-header.txt"):
        if not os.path.isfile(os.path.join(templates_dir, frag)):
            problems.append("missing fragment: templates/%s" % frag)
    return problems


def validate_manifest(root=None):
    """Assert the manifest is well-formed and covers every shipped output."""
    root = root or _repo_root()
    problems = []
    man_path = os.path.join(root, "ownership.json")
    if not os.path.isfile(man_path):
        return ["ownership.json not found"]
    try:
        manifest = load_manifest(man_path)
    except ConfigError as exc:
        return [str(exc)]
    valid_owners = {"framework", "project", "conditional", "ignore"}
    for rule in manifest.rules:
        if "glob" not in rule or "owner" not in rule:
            problems.append("manifest rule missing glob/owner: %r" % rule)
        elif rule["owner"] not in valid_owners:
            problems.append("manifest rule has invalid owner: %r" % rule)
    templates_dir = os.path.join(root, "templates")
    if os.path.isdir(templates_dir):
        for rel in iter_template_files(templates_dir):
            out = template_to_output(rel)
            if out is None:
                continue
            if manifest._match(out) is None:
                problems.append("manifest does not classify output: %s" % out)
    return problems
