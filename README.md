# ResearchPartner

A reusable **operating layer** for doing research with Claude as a collaborator. ResearchPartner turns a **Claude Project** (claude.ai) + **Claude Code** into a consistent "Research Partner": a shared docs knowledge base, a mode/rule system, prompt patterns, and a consistency guard — all configured for *your* project by an interactive setup.

It is distributed as a **base template you clone into your own private repository**. The base stays generic; your clone holds your research.

## How it works (the two-tool model)

- **Claude Project (in claude.ai)** — the thinking seat. It reads your `docs/` and acts as the Research Partner: plans experiments, analyzes results, and writes the prompts you hand to Claude Code. Replies in your chosen language, conclusion first.
- **Claude Code** — the hands. It runs in your repo, executes those prompts (edits code, runs experiments), and reads `docs/` directly from disk.
- **`docs/`** — the single source of truth both share, kept internally consistent by `make docs-check`.

You drive the loop; the docs keep both tools in sync across sessions.

## Prerequisites

- **Python 3.8+** and **git** (no third-party Python packages).
- A **Claude account with Projects** (for the Project seat) and **Claude Code** installed (for the execution seat).
- A place for a **private** git repo on your account (GitHub or similar). Your research is private; only the *base* template is public.

## Setup, step by step

### 1. Make your own private copy

The base is public; your instance must be private.

**First, create a new EMPTY private repository on GitHub** — no README, no license, no `.gitignore`, just the bare repo (e.g. `<you>/my-research`). You will push to it in step 4, so it must exist first (otherwise `git push` reports "Repository not found").

Then clone the base, detach it as `upstream`, and point `origin` at the empty repo you just created:

```bash
git clone https://github.com/koba-jon/ResearchPartner.git my-research   # local dir name is up to you
cd my-research
git remote rename origin upstream                       # keep the base as 'upstream' for updates
git remote add origin https://github.com/<you>/my-research.git   # the EMPTY private repo from above
```

(Prefer to let setup do the rename? Skip the `git remote rename` line and pass `--adopt-base-as-upstream` to `init.py` in step 3.)

### 2. Place it inside your project workspace

Move the clone so it sits **inside** your project's working directory (the folder that holds your code, data, and results). A typical layout:

```
my-research/                 <- your workspace (PROJECT_ROOT)
├── src/                     <- your code
├── data/  results/  ...
└── ResearchPartner/         <- this clone (holds docs/ + scripts)
```

```bash
mv ResearchPartner /path/to/my-research/
cd /path/to/my-research/ResearchPartner
```

### 3. Configure (interactive)

```bash
python3 scripts/init.py        # or: make init   (add --adopt-base-as-upstream if you skipped the rename)
```

It interviews you in a few phases and then renders your configured instance:

- **Working location & compute** — your `PROJECT_ROOT`, where Claude Code task artifacts go, and your compute environment (Colab / local-GPU / local-CPU / other).
- **Detect & ingest** — a read-only scan of your workspace so the docs start with an accurate picture (no code yet? it asks a few intent questions instead).
- **Identity** — project name, your name, and languages (chat reply language, docs language, code/prompt language).
- **Options** — source mirror, Auto mode, a generated manual, and the labels for "one experiment" / "one recorded finding" (defaults: Experiment / Note).

`init.py` then renders `docs/`, writes `researchpartner.config.json` and `project-instructions.txt`, installs the git hook, and makes **one** commit. It **never pushes** and **never creates a remote** — you control your private history. (Re-run safely with `--dry-run` to preview, or `--print-config` to see resolved settings.)

### 4. Push to your private repo

```bash
git push -u origin main
```

### 5. Wire into Claude Code

Claude Code reads `docs/` straight from the repo, so there is nothing to upload — just run Claude Code in your workspace. When you ask the Research Partner (in the Project) for a task, it produces a Claude Code prompt that already carries the canonical path-variable header from `docs/entrypoint.md` section 0; paste that prompt into Claude Code and run it.

### 6. Set up the Claude Project

1. In **claude.ai**, create a new **Project** for your research.
2. Open the Project's **custom instructions** and paste the entire contents of **`project-instructions.txt`** (rendered at your repo root in step 3). This is what makes Claude behave as your Research Partner: read `docs/entrypoint.md` first each session, reply in your language, follow the modes and rules.
3. **Give the Project access to your `docs/`** so it can actually follow "read `docs/entrypoint.md` first." Pick whichever your setup supports:
   - **Connect the repo (best):** if you use a repository/GitHub connector (or an MCP server that exposes the repo), connect your private ResearchPartner repo. The Research Partner can then open `docs/entrypoint.md` and pull other docs on demand.
   - **Add docs as Project knowledge:** upload the `docs/` tree to the Project's knowledge (at minimum `docs/entrypoint.md` and the files it routes to). Re-upload after large doc changes or a `make update`.
   - **Paste on demand (minimal):** if you have neither, paste `docs/entrypoint.md` at the start of a session; the Research Partner will name the specific files it needs and you paste those.

Order matters only here: push (step 4) before connecting the repo connector, since the connector reads what is on your remote.

### 7. Your first session

Start a conversation in the Project. The Research Partner reads `docs/entrypoint.md`, summarizes the current state in a few lines, and asks what you want to do — classifying it into a mode (Investigate / Design / Implement / Experiment / Analyze / Write, plus Auto and Maintain). For execution work it hands you a Claude Code prompt; you run it; then you (or it) record the result back into `docs/` and run `make docs-check`.

A good first move: ask it to help you fill in `docs/concepts/core-concepts.md` and `docs/project/project-status.md` for your project — those scaffolds ship with prompts that walk you through it.

## Day to day and maintenance

```bash
make docs-check     # verify the docs are internally consistent (also runs on every commit)
make update         # after `git fetch upstream && git merge upstream/main`: pull framework
                    #   improvements WITHOUT touching your research notes (your edits to a
                    #   framework file are preserved as *.rp-new to merge, never clobbered)
make sync-src       # if you enabled the source mirror: refresh src/ from your workspace
make help           # list all targets
```

No `make`? Every target is a thin wrapper — run the script directly (e.g. `python3 scripts/check_docs_consistency.py`). See `SETUP.md` section 11.

Want GitHub Actions CI on your repo? The template ships CI as an inert `ci.example.yml` (not an active workflow, so cloning and pushing with a standard token never hits GitHub's `workflow`-scope wall). Enable it by adding that YAML as `.github/workflows/ci.yml` via GitHub's web UI. See `ci.example.yml` for the one-step instructions.

## What you get

- `docs/entrypoint.md` — the single startup file the Research Partner reads first.
- `docs/operations/**` — the modes, rules, prompt factory, time estimation, and the consistency-guard contract.
- `docs/concepts|method|evaluation|project|writing/**` — scaffolds you fill in for your domain (each with worked examples to copy).
- `project-instructions.txt` — paste-ready Claude Project instructions.
- `scripts/` + `ownership.json` — the engine, the guard, and the framework/project ownership split that makes `make update` safe.

## More

- Full lifecycle, all CLI flags, and troubleshooting: **`SETUP.md`**.
- Maintainers (tests, CI, editing the base): `SETUP.md` sections 10-11; `CHANGELOG.md`.
- License: MIT (see `LICENSE`).
