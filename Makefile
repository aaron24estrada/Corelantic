API := apps/api
WEB := apps/web

.PHONY: install hooks dev-api dev-web lint format typecheck test check client validate

install:
	uv sync --directory $(API)
	npm install --prefix $(WEB)

# Install git pre-commit hooks (requires pre-commit: `uv tool install pre-commit`).
hooks:
	pre-commit install

# Regenerate the typed API client from the backend's OpenAPI schema.
client:
	uv run --directory $(API) python scripts/export_openapi.py
	npm run gen:api --prefix $(WEB)

dev-api:
	uv run --directory $(API) corelantic-api

dev-web:
	npm run dev --prefix $(WEB)

lint:
	uv run --directory $(API) ruff check .
	npm run lint --prefix $(WEB)

format:
	uv run --directory $(API) ruff format .
	npm run format --prefix $(WEB)

typecheck:
	uv run --directory $(API) mypy
	npm run typecheck --prefix $(WEB)

test:
	uv run --directory $(API) pytest
	npm test --prefix $(WEB)

# Validate the semantic registry (references, formulas, joins, synonyms, duplicates).
validate:
	uv run --directory $(API) python scripts/validate_registry.py

check: lint typecheck test
