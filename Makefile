# One command each. Python via uv (3.12), Node 20.
export APP_ENV ?= dev
UV := uv run --project backend
NPM := npm --prefix web

.PHONY: setup seed run web test e2e lint bench foundation-diff

setup:            ## install backend and frontend dependencies (+ Playwright Chromium)
	uv sync --project backend
	$(NPM) ci
	$(NPM) exec -- playwright install chromium

seed:             ## reset the SQLite database in place and seed every registered app
	$(UV) python -m backend.seed

run:              ## API on :8000 (APP_ENV=dev enables the mock sign-in)
	$(UV) uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

web:              ## Vite dev server on :5173 (proxies /api to :8000)
	$(NPM) run dev

test:             ## backend unit/integration tests
	$(UV) pytest backend/tests

e2e:              ## Playwright (starts API and web itself; seeds a fresh e2e database)
	$(NPM) run e2e

lint:             ## ruff, eslint, tsc
	$(UV) ruff check backend scripts
	$(UV) ruff format --check backend scripts
	$(NPM) run lint
	$(NPM) run typecheck

bench:            ## p95 of list, filter and search against a seeded API on :8000
	$(UV) python -m backend.bench

foundation-diff:  ## lines changed under backend/platform and web/src/platform vs main
	$(UV) python scripts/foundation_diff.py
