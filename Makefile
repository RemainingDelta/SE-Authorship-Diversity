.PHONY: help install lint fix test ci clean

help:
	@echo "make install  install Python dependencies"
	@echo "make lint     ruff lint on src/"
	@echo "make fix      ruff format + autofix on src/"
	@echo "make test     run pytest"
	@echo "make ci       run everything CI runs"
	@echo "make clean    remove caches"

install:
	pip install -r requirements.txt

lint:
	ruff check src/

fix:
	ruff check --fix src/
	ruff format src/

test:
	pytest tests/

ci:
	@ruff check src/
	@ruff format --check src/ || (echo "Python files need formatting — run: make fix" && exit 1)
	@pytest tests/

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# TODO(dashboard-ticket): add `up` (cd app && npm run dev) and frontend lint/format
# to lint, fix, and ci once app/ exists, like se-author-gender-diversity.
