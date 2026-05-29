# Changelog

All notable changes to the ResearchPartner base template. The format follows
[Keep a Changelog](https://keepachangelog.com/); this project versions the
framework, not any individual clone (a clone records its own history in git).

## [Unreleased]

### Added
- Initial public base template: zero-dependency (stdlib-only) Python engine
  (`{{TOKEN}}` substitution, line/inline conditionals, single-source `<!-- include -->`
  fragments, transactional whole-tree render).
- Eight-mode operating taxonomy: six lifecycle modes (Investigate, Design,
  Implement, Experiment, Analyze, Write) plus two cross-cutting modes (Auto,
  Maintain). Result ingestion folds into Experiment, critical verification into
  Analyze, reflection into Maintain. Each mode has its own protocol file under
  `docs/operations/` (e.g. `implement-mode.md`), and `operation-modes.md` is the
  router that links all eight.
- Publish closing step (`ENABLE_PUBLISH_STEP`, default `yes`): the prompt-factory
  ends generated Claude Code prompts with a Publish step so that, *after the task's
  Verification passes*, it mirrors `src/` and commits+pushes the docs repo (never
  the non-git workspace). It assumes the one-time `origin` setup (README step 4) is
  done; set it to `no` to keep commit/push manual. Publish never substitutes for
  Verification.
- First-session onboarding: a self-clearing "First-session setup" block in
  `docs/entrypoint.md`. On the first session the Research Partner offers to
  bootstrap the docs from existing artifacts (prior results, logs, notebooks,
  writeups) via a read-only Claude Code ingest (`prompt-factory` section 4.7),
  and -- for a non-English `DOCS_LANG` -- a one-time localization (section 4.6).
  Both ask first, and the block is removed once done.
- Base lint now flags single-brace token leaks (`${TOKEN}` where a `{{TOKEN}}`
  was meant), the bug class behind two worked-example / path-table defects;
  covered by a new `tests/test_lint.py`.
- Private-clone distribution: clone the base, detach to `upstream`, configure
  with `scripts/init.py` (phased interview + read-only workspace ingest), push to
  your own private repo. `init` never pushes and never creates a remote.
- Ownership manifest (`ownership.json`): framework-owned files are re-rendered by
  `make update`; project-owned files are seeded once and never overwritten; a
  locally-edited framework file is preserved as `*.rp-new` instead of clobbered.
- Consistency guard (`make docs-check`): required files, link + backtick-path
  resolution, section references, the two byte-identical mirror blocks, router
  reachability, and an evolution/maintenance log-count check. Docs are
  language-agnostic (Unicode) -- no character/script policy.
- Optional subsystems (configurable): source mirror, Auto mode, generated
  `GETTING_STARTED.md` manual.
- First-class documentation playbook with multi-domain worked examples.
- Test suite (`make test`, stdlib `unittest`). CI is shipped as an inert
  `ci.example.yml` (opt-in: add as `.github/workflows/ci.yml` via the GitHub web
  UI) so that cloning and pushing with a standard token never hits GitHub's
  `workflow`-scope restriction; it runs lint-base + the suite on Python 3.8-3.12.

### Changed
- `init` interview is clearer and shorter: every prompt now carries a one-line
  explanation of what it sets, and the project root, task-artifacts folder, and
  project name are offered as a confirm-or-edit (accept the detected default with
  `yes`, or answer `no` to type your own).
- The docs character/script policy (and its `DOCS_LANG_IS_ASCII` flag) is removed:
  docs are language-agnostic (Unicode), so Greek math letters and any non-Latin
  script are always allowed. A non-English `DOCS_LANG` now seeds a one-time
  localization offer (a localization line in the first-session setup block of
  `docs/entrypoint.md`, backed by a `prompt-factory` section 4.6 skeleton); the
  skeleton still ships in English because the engine has no translation step.
- `init` no longer asks for the experiment/record label nouns; they default to
  `Experiment` / `Note` (override `EXPERIMENT_UNIT_LABEL` / `ANALYSIS_RECORD_LABEL`
  in config if a project prefers other nouns).
- `init` no longer asks whether to generate the GETTING_STARTED manual or to enable
  Auto mode; both are on by default now. `ENABLE_AUTO_MODE`'s default flipped from
  `no` to `yes` — set it to `no` in config to omit the Auto mode subsystem.
- The source mirror is no longer a question: `init` enables it automatically when a
  `PROJECT_ROOT/src` directory exists and skips it otherwise — matching what
  `sync_src` actually mirrors. Set `SRC_MIRROR_ENABLED=no` in config to opt out.
- Documentation consolidated into a single `README.md`: it gains an Operating-modes
  overview table, the `init` CLI flag reference, troubleshooting, non-interactive
  setup, and a maintainers section. `SETUP.md` was removed and its unique content
  folded into `README.md`.

### Fixed
- `docs/project/project-status.md` referenced the wrong file for the verdict
  vocabulary; corrected to `docs/evaluation/evaluation-and-visualization.md`
  section 2.
- `init --dry-run` no longer performs `git remote rename` under
  `--adopt-base-as-upstream`; a dry run now writes nothing.
- `load_manifest` raises a clean error on a malformed `ownership.json` instead
  of a raw traceback (it runs in the pre-commit hook).
- The consistency guard no longer flags a titled markdown link
  `[x](f.md "title")` as a missing target.
- Free-text intake fields (`INTENT_*`, `INGEST_SUMMARY`) containing a literal
  `{{...}}` no longer abort the whole render.
- An all-non-ASCII project name now yields a stable, distinct shell-variable
  stem (was a fixed `PROJECT` that collided across names), and interactive `init`
  accepts non-ASCII `PROJECT_NAME` display names instead of re-prompting forever.
- `forbidden-actions` now references `algorithmic-levers` section 3 (rejected
  approaches), resolving a dangling cross-reference; the Publish step no longer
  assumes the source mirror; dropped the unused `INGEST_TREE` token.

[Unreleased]: https://github.com/koba-jon/ResearchPartner/commits/main
