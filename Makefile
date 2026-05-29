.PHONY: help docs-check install-hooks init update sync-src lint-base test

INSTANCE ?= .
ARGS ?=

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN{FS=":.*## "}{printf "  %-14s %s\n", $$1, $$2}'

docs-check:  ## Run the docs consistency guard on INSTANCE (default .)
	python3 scripts/check_docs_consistency.py --instance $(INSTANCE)

install-hooks:  ## Point git at the versioned hooks in .githooks
	git config core.hooksPath .githooks
	@echo "Installed repository hooks from .githooks"

init:  ## Configure this clone interactively (one-time). Pass flags via ARGS=...
	python3 scripts/init.py $(ARGS)

update:  ## Re-render framework-owned files after merging upstream. ARGS=...
	python3 scripts/update.py $(ARGS)

sync-src:  ## Mirror code from PROJECT_ROOT into src/ (if SRC_MIRROR_ENABLED). ARGS=...
	python3 scripts/sync_src.py $(ARGS)

lint-base:  ## (base only) Lint templates, manifest, and token sanity
	python3 scripts/lint_base.py

test:  ## (base only) Run the test suite (stdlib unittest; no deps)
	python3 -m unittest discover -s tests -p 'test_*.py'
