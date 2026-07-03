API := apps/api
WEB := apps/web

.PHONY: install dev-api dev-web lint format typecheck test check

install:
	uv sync --directory $(API)
	npm install --prefix $(WEB)

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
