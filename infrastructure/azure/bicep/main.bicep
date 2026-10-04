targetScope = 'subscription'

@description('Short name used in Azure resource names (lowercase, 3–12 chars).')
@minLength(3)
@maxLength(12)
param environmentName string = 'agentic'

@description('Azure region for all resources.')
param location string = 'eastus'

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'agenticadmin'

@secure()
@description('PostgreSQL administrator password.')
param postgresAdminPassword string

@description('Deploy Azure Cache for Redis (recommended for production WebSocket scaling).')
param deployRedis bool = true

@description('App Service plan SKU (e.g. B1, S1).')
param appServicePlanSku string = 'B1'

@description('Static Web App SKU: Free or Standard.')
@allowed(['Free', 'Standard'])
param staticWebAppSku string = 'Free'

var resourceGroupName = 'rg-${environmentName}-inventory-ai'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    project: 'AgenticInventoryAI'
    environment: environmentName
  }
}

module postgres 'postgres.bicep' = {
  scope: rg
  name: 'postgres'
  params: {
    location: location
    environmentName: environmentName
    adminLogin: postgresAdminLogin
    adminPassword: postgresAdminPassword
  }
}

module redis 'redis.bicep' = if (deployRedis) {
  scope: rg
  name: 'redis'
  params: {
    location: location
    environmentName: environmentName
  }
}

module backend 'app-service.bicep' = {
  scope: rg
  name: 'backend'
  params: {
    location: location
    environmentName: environmentName
    planSku: appServicePlanSku
    databaseHost: postgres.outputs.serverFqdn
    databaseName: postgres.outputs.databaseName
    databaseUser: postgresAdminLogin
    databasePassword: postgresAdminPassword
    redisHostName: deployRedis ? redis!.outputs.hostname : ''
    redisPrimaryKey: deployRedis ? redis!.outputs.primaryKey : ''
  }
}

module frontend 'static-web-app.bicep' = {
  scope: rg
  name: 'frontend'
  params: {
    location: location
    environmentName: environmentName
    sku: staticWebAppSku
  }
}

output resourceGroupName string = rg.name
output backendUrl string = backend.outputs.httpsUrl
output frontendUrl string = frontend.outputs.defaultHostname
output postgresServerFqdn string = postgres.outputs.serverFqdn
output deploymentNotes string = 'Run database migrations after first backend deploy: alembic upgrade head'
