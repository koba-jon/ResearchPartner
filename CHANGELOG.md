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

[Unreleased]: https://github.com/
