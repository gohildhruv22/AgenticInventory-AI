# Azure Deployment (AgenticInventory AI)

This folder contains infrastructure-as-code and CI templates to deploy the platform to Azure **without Docker**. The target architecture uses managed Azure services:

| Component | Azure service |
|-----------|----------------|
| Frontend (React/Vite SPA) | Azure Static Web Apps |
| Backend (FastAPI) | Azure App Service (Linux, Python 3.11) |
| Database | Azure Database for PostgreSQL — Flexible Server 16 |
| Cache | Azure Cache for Redis (optional, recommended) |

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az`) logged in
- Subscription with permission to create resources
- [Bicep CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install) (included with recent `az` versions)

## 1. Provision infrastructure (Bicep)

Copy and edit parameters:

```powershell
Copy-Item infrastructure/azure/parameters.example.json infrastructure/azure/parameters.json
# Edit parameters.json — set a strong postgresAdminPassword
```

Deploy at subscription scope:

```powershell
az deployment sub create `
  --name agenticinventory-infra `
  --location eastus `
  --template-file infrastructure/azure/bicep/main.bicep `
  --parameters @infrastructure/azure/parameters.json
```

Note deployment outputs:

- `backendUrl` — App Service API hostname
- `frontendUrl` — Static Web App URL
- `postgresServerFqdn` — PostgreSQL host

## 2. Configure App Service application settings

After infrastructure is created, set secrets and integration keys in the backend App Service (`app-<env>-inv-api`):

| Setting | Description |
|---------|-------------|
| `JWT_SECRET_KEY` | Strong random secret (64+ chars) |
| `GROQ_API_KEY` | Groq LLM API key |
| `CORS_ORIGINS` | JSON array including your Static Web App URL, e.g. `["https://swa-agentic-inv.azurestaticapps.net"]` |
| `FRONTEND_BASE_URL` | Static Web App URL (for email deep links) |
| `NEWS_API_KEY`, `OPENWEATHER_API_KEY`, `CALENDARIFIC_API_KEY` | Optional intelligence APIs |
| `SMTP_*`, `ADMIN_NOTIFICATION_EMAIL` | Email integration |
| `IMAP_*` (via Settings UI / DB) | Supplier ETA ingestor |

`DATABASE_URL` and `REDIS_URL` are set by Bicep where applicable. Override only if you rotate credentials.

Example (Azure CLI):

```powershell
$rg = "rg-agentic-inventory-ai"
$app = "app-agentic-inv-api"

az webapp config appsettings set -g $rg -n $app --settings `
  JWT_SECRET_KEY="<generate-secure-secret>" `
  GROQ_API_KEY="<your-groq-key>" `
  FRONTEND_BASE_URL="https://<your-swa-host>" `
  CORS_ORIGINS='["https://<your-swa-host>"]'
```

## 3. Deploy backend (App Service)

Package the `backend/` directory so `app/` is at the zip root:

```powershell
cd backend
Compress-Archive -Path * -DestinationPath ../backend-deploy.zip -Force
cd ..

az webapp deployment source config-zip `
  -g rg-agentic-inventory-ai `
  -n app-agentic-inv-api `
  --src backend-deploy.zip
```

Run migrations (Kudu SSH, local tunnel, or one-off command):

```powershell
az webapp ssh -g rg-agentic-inventory-ai -n app-agentic-inv-api
# In the remote shell:
cd /home/site/wwwroot
python -m alembic upgrade head
```

Health check: `GET https://<backendUrl>/api/v1/health`

## 4. Deploy frontend (Static Web App)

Build with production API endpoints:

```powershell
cd frontend
$env:VITE_API_BASE_URL="https://app-agentic-inv-api.azurewebsites.net/api/v1"
$env:VITE_WS_URL="wss://app-agentic-inv-api.azurewebsites.net/ws"
npm ci
npm run build
```

Deploy `frontend/dist` using the Static Web Apps deployment token:

```powershell
az staticwebapp secrets list -n swa-agentic-inv -g rg-agentic-inventory-ai --query "properties.apiKey" -o tsv
# Use SWA CLI or Azure DevOps/GitHub Action with the deployment token
npx @azure/static-web-apps-cli deploy ./dist --deployment-token <token> --env production
```

## 5. CI/CD pipeline

`infrastructure/azure/pipelines/azure-pipelines.yml` defines:

- **Build** — backend tests, frontend build
- **Deploy** — disabled by default (`deployEnabled: false`); enable when ready

Set pipeline variables for resource group, app names, and service connection before enabling deploy stages.

## Local development (no Docker)

Use SQLite for zero-setup local dev (see root `.env.example`) or point `DATABASE_URL` at an Azure PostgreSQL instance for shared dev.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

## Security checklist before production

- [ ] Rotate `JWT_SECRET_KEY` and store in App Service / Key Vault
- [ ] Restrict PostgreSQL firewall to App Service outbound IPs if required
- [ ] Enable Redis TLS only (`rediss://` — configured in Bicep)
- [ ] Set `DEBUG=false`
- [ ] Configure custom domains and managed certificates
- [ ] Review `SUPPLIER_OVERRIDE_EMAIL` for production routing

## Troubleshooting

| Issue | Action |
|-------|--------|
| 502 on API | Check App Service logs → Log stream; verify `uvicorn` startup command |
| CORS errors | Add SWA origin to `CORS_ORIGINS` on App Service |
| WebSocket fails | Ensure `wss://` URL; App Service supports WebSockets — enable in Configuration |
| DB connection failed | Confirm firewall rule `AllowAzureServices`; verify `ssl=require` in connection string |
