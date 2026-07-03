API := apps/api
WEB := apps/web

.PHONY: install dev-api dev-web lint format typecheck test check client

install:
	uv sync --directory $(API)
	npm install --prefix $(WEB)

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

check: lint typecheck test
