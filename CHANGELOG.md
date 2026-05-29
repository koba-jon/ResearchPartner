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
  Analyze, reflection into Maintain.
- Optional Publish closing step (`ENABLE_PUBLISH_STEP`, default `no`): when
  enabled, the prompt-factory grows a Publish section so a generated Claude Code
  prompt mirrors `src/` and commits+pushes the docs repo after verification
  (never the non-git workspace).
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
  reachability, an evolution/maintenance log-count check, and a `DOCS_LANG_IS_ASCII`
  -gated non-ASCII-letter check.
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
- The docs character-policy question (`DOCS_LANG_IS_ASCII`) is no longer asked;
  `init` derives it from your docs language (e.g. Japanese → `no`). The guard
  itself is unchanged — override the value in config if you ever need to.
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

[Unreleased]: https://github.com/koba-jon/ResearchPartner/commits/main
