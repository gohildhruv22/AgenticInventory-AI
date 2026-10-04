# Quickstart: AgenticInventory AI

**Phase**: 1 — Design & Contracts
**Date**: 2026-05-17

## Prerequisites

- **Python** 3.11+
- **Node.js** 20+ (with npm)
- **Docker** and **Docker Compose** (for PostgreSQL, Redis, ChromaDB)
- **Git**

## 1. Clone & Setup

```bash
git clone <repo-url>
cd AgenticInventory-AI
```

## 2. Start Infrastructure Services

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

This starts:
- **PostgreSQL 16** on port 5432
- **Redis 7** on port 6379
- **ChromaDB** on port 8000

## 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp ../.env.example .env
```

Edit `.env` with your API keys:
```env
# Required
GROQ_API_KEY=your-groq-api-key
SECRET_KEY=your-secret-key-min-32-chars

# External APIs
GOOGLE_TRENDS_ENABLED=true
NEWS_API_KEY=your-newsapi-key
WEATHER_API_KEY=your-openweathermap-key
HOLIDAY_API_KEY=your-calendarific-key

# Database (defaults match docker-compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agenticinventory
REDIS_URL=redis://localhost:6379/0
CHROMADB_URL=http://localhost:8000

# SMTP (optional for dev — emails will be logged instead)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
```

```bash
# Run database migrations
alembic upgrade head

# Seed demo data (optional)
python -m app.seed

# Start the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 4. Start Celery Worker

In a separate terminal:
```bash
cd backend
source .venv/bin/activate
celery -A celery_app.worker worker --loglevel=info --beat
```

## 5. Frontend Setup

In a separate terminal:
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs on `http://localhost:5173`.

## 6. Verify Everything Works

1. Open `http://localhost:5173` — you should see the landing page with dark theme and gradient accents
2. Register a new account
3. Navigate to Dashboard — you should see the main dashboard with KPI cards
4. Go to Inventory — seed data should show inventory items
5. Trigger a pipeline (lower an item's stock below threshold or use the manual trigger)
6. Watch the Agent Workflow Visualization page for live pipeline updates

## 7. API Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Expected:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "chromadb": "connected",
    "celery": "connected"
  }
}
```

## Development Commands

| Command | Purpose |
|---------|---------|
| `make dev` | Start all services (docker + backend + frontend) |
| `make test` | Run all tests (backend + frontend) |
| `make test-backend` | Run pytest |
| `make test-frontend` | Run vitest |
| `make lint` | Lint all code |
| `make migrate` | Run Alembic migrations |
| `make seed` | Seed demo inventory data |
| `make docker-up` | Start infrastructure containers |
| `make docker-down` | Stop infrastructure containers |

## Project URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| ChromaDB | localhost:8000 |
