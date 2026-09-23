# Housekeeping targets. Run from the repository root.

.PHONY: clean help

# Directories never searched or touched by clean: virtualenvs, VCS metadata,
# and untracked local data (live-tree backups, research output, scratch work).
PRUNE := -path ./.git -o -path ./.venv -o -path ./venv -o -path ./venv_linux \
	-o -path ./backup -o -path ./output -o -path ./scratchpad -o -path ./docker

help:
	@echo "make clean  remove caches and build output (keeps venvs, .env, backup/, output/)"

clean:
	@# Recursive caches: prune the protected trees, then delete every match at any depth.
	@find . \( $(PRUNE) \) -prune -o \
		\( -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \
			-o -name .mypy_cache -o -name htmlcov -o -name '*.egg-info' \) \
		-o -type f \( -name '*.py[co]' -o -name .DS_Store \) \) \
		-prune -exec rm -rf {} +
	@# Top-level build and coverage output.
	@rm -rf site build dist .coverage .coverage.* coverage.xml
	@echo "clean: done"
