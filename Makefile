.PHONY: dev backend frontend migrate seed test lint build setup setup-backend setup-frontend clean

# ─── Development ──────────────────────────────────────────
dev:
	@echo "Starting backend and frontend (no Docker required)..."
	$(MAKE) -j2 backend frontend

backend:
	cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# ─── Database ─────────────────────────────────────────────
migrate:
	cd backend && .venv/Scripts/python -m alembic upgrade head

migration:
	cd backend && .venv/Scripts/python -m alembic revision --autogenerate -m "$(msg)"

seed:
	@echo "Seed via API: POST /api/v1/inventory/seed (requires auth)"

# ─── Testing ─────────────────────────────────────────────
test: test-backend test-frontend

test-backend:
	cd backend && .venv/Scripts/python -m pytest -q

test-frontend:
	cd frontend && npm run test -- --run

# ─── Linting ─────────────────────────────────────────────
lint: lint-backend lint-frontend

lint-backend:
	cd backend && .venv/Scripts/python -m ruff check .
   
lint-frontend:
	cd frontend && npx tsc --noEmit && npx eslint src/

# ─── Build ───────────────────────────────────────────────
build: build-backend build-frontend

build-backend:
	@echo "Backend: package backend/ for Azure App Service zip deploy (see infrastructure/azure/README.md)"

build-frontend:
	cd frontend && npm run build

# ─── Setup ───────────────────────────────────────────────
setup: setup-backend setup-frontend

setup-backend:
	cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt

setup-frontend:
	cd frontend && npm install

# ─── Clean ───────────────────────────────────────────────
clean:
	cd frontend && rm -rf dist node_modules/.cache
	cd backend && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
