# ResearchPartner Setup & Lifecycle

This is the full guide. For the short version see `README.md`.

## 1. Concept

ResearchPartner is a **base template**. You never run the base directly; you clone it into your own private repository and configure that clone for one research project. The base ships only `templates/` (no top-level `docs/`), so pulling future framework updates can never conflict with your rendered docs.

Two ownership classes (see `ownership.json`):

- **framework-owned** — the operating layer (`docs/operations/**`, `docs/entrypoint.md`, scripts). Re-rendered by `make update`.
- **project-owned** — your research state (status, comparison, records, backlog, concept/method bodies). Yours forever; never auto-touched.

## 2. Requirements

- Python 3.8 or newer (stdlib only — no `pip install`).
- git.
- `make` is optional. Every `make <target>` is a thin wrapper; without `make` (e.g. on Windows) run the script directly: `make docs-check` = `python3 scripts/check_docs_consistency.py`, `make init` = `python3 scripts/init.py`, `make update` = `python3 scripts/update.py`, `make sync-src` = `python3 scripts/sync_src.py`, `make install-hooks` = `git config core.hooksPath .githooks`.

## 3. First-time setup

1. **Clone & detach the base.**
   ```bash
   git clone https://github.com/<owner>/ResearchPartner.git
   cd ResearchPartner
   git remote rename origin upstream
   ```
2. **Create your private repo** on your account and point `origin` at it:
   ```bash
   git remote add origin https://github.com/<you>/<your-private-name>.git
   ```
   (Or skip steps 1's rename and 2, and let `init.py --adopt-base-as-upstream` do the rename.)
3. **Place the clone in your workspace.** The usual layout is `PROJECT_ROOT/ResearchPartner`, where `PROJECT_ROOT` is your project's working directory (code, data, results).
4. **Configure:**
   ```bash
   python3 scripts/init.py          # or: make init
   ```
   The interview has four phases: working location & compute; a read-only scan of your workspace; (if no code is found) a short intent interview; identity (names, languages); and options (manual, src mirror, experiment/record labels, Auto mode).
5. **Wire into Claude:** run Claude Code in the repo (it reads `docs/` directly, no upload needed), and create a Claude Project whose custom instructions are the full contents of `project-instructions.txt`. Then give the Project access to your `docs/` — connect the repo via a connector, add `docs/` as Project knowledge, or paste `docs/entrypoint.md` at the start of a session. See the step-by-step "Setup, step by step" walkthrough in `README.md` for the exact order.
6. **Push when ready:**
   ```bash
   git push -u origin main
   ```

### Non-interactive setup

```bash
python3 scripts/init.py --non-interactive --config my.config.json
```
Use `researchpartner.config.example.json` as a starting point. `--dry-run` shows the planned writes without touching disk; `--print-config` shows the fully-resolved config.

## 4. Daily use

- Start a Claude Chat session — the Research Partner reads `docs/entrypoint.md` first.
- Generate Claude Code prompts via `docs/operations/prompt-factory.md`.
- Record results in `docs/evaluation/comparison.md`, `docs/project/project-status.md`, and `docs/project/themes/`.
- Run `make docs-check` after editing docs (the pre-commit hook also runs it).

## 5. Pulling framework updates

```bash
git fetch upstream
git merge upstream/main
make update        # re-render framework-owned files only
make docs-check
```
If you had hand-edited a framework file, `make update` does **not** overwrite it — it writes the new version next to it as `<file>.rp-new` and warns. Compare, merge, delete the `.rp-new`.

## 6. The source mirror (optional)

If you enabled `SRC_MIRROR_ENABLED`, `make sync-src` mirrors your workspace source into `src/` (content-hash compare; never deletes without `--prune`). The mirror is read-only — edit the real source in your workspace, then re-sync.

## 7. The consistency guard

`make docs-check` runs `scripts/check_docs_consistency.py`: required files exist, markdown links resolve, section references resolve, routers reach their bodies, the two byte-identical mirror blocks match, and (when your docs language is ASCII) a no-CJK policy. Install the hook once with `make install-hooks` (init does this for you).

## 8. CLI reference (`scripts/init.py`)

| Flag | Effect |
|---|---|
| `--non-interactive` | ask nothing; requires `--config` |
| `--config <path>` | load answers from JSON |
| `--dry-run` | show planned writes; write nothing |
| `--print-config` | print the resolved config and exit |
| `--adopt-base-as-upstream` | rename `origin`->`upstream`, then configure |
| `--force` | configure even over the base marker / an existing `docs/` |
| `--skip-commit` | render and configure, but do not commit |
| `--skip-git` | touch no git state at all |

## 9. Troubleshooting

- **"docs/ already exists and is non-empty"** — you are re-running init over a configured clone. Pass `--force` only if you really mean to re-render.
- **"This looks like the ResearchPartner BASE repo"** — you are running init on the base. Make your private repo first, or pass `--adopt-base-as-upstream`.
- **Guard fails on CJK** — set `DOCS_LANG_IS_ASCII=no` in your config if your docs are written in a non-ASCII script.
- **A mirror block "drift" error** — you edited one copy of a byte-identical block by hand; re-run `make update` to re-render from the single-source fragment.

## 10. Updating the base itself (maintainers)

Edits to `templates/` and `scripts/` are linted on commit by `make lint-base` (token sanity, manifest coverage, fragment presence, and a render of every template to catch unbalanced conditionals). Run `make lint-base` before pushing the base.

## 11. Tests and CI (maintainers)

The framework ships a stdlib-only test suite (no third-party deps):

```bash
make test        # = python3 -m unittest discover -s tests -p 'test_*.py'
```

It covers the engine (tokens, conditionals, includes), the config/derivation layer, the ownership manifest, the consistency guard (a good clone passes; each defect class — mirror drift, dangling backtick path, non-ASCII letters, missing required file, broken router — fails), and end-to-end lifecycle round-trips (`init`, `update` `.rp-new` safety, `sync_src`, base-protection, the leanest/all-on render matrix). GitHub Actions (`.github/workflows/ci.yml`) runs `lint-base` + the suite across Python 3.8-3.12 on every push and pull request.
