param location string
param environmentName string
param planSku string
param databaseHost string
param databaseName string
param databaseUser string

@secure()
param databasePassword string

param redisHostName string = ''
param redisPrimaryKey string = ''

var planName = 'asp-${environmentName}-inv'
var appName = 'app-${environmentName}-inv-api'

var databaseUrl = 'postgresql+asyncpg://${databaseUser}:${databasePassword}@${databaseHost}:5432/${databaseName}?ssl=require'

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: {
    name: planSku
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: planSku != 'F1' && planSku != 'FREE'
      appCommandLine: 'python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      webSocketsEnabled: true
      appSettings: concat(
        [
          {
            name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
            value: 'true'
          }
          {
            name: 'WEBSITE_RUN_FROM_PACKAGE'
            value: '0'
          }
          {
            name: 'DATABASE_URL'
            value: databaseUrl
          }
          {
            name: 'DEBUG'
            value: 'false'
          }
          {
            name: 'AUTONOMOUS_LOOP_ENABLED'
            value: 'true'
          }
        ],
        !empty(redisHostName)
          ? [
              {
                name: 'REDIS_URL'
                value: 'rediss://:${redisPrimaryKey}@${redisHostName}:6380/0'
              }
            ]
          : []
      )
    }
  }
}

output defaultHostname string = webApp.properties.defaultHostName
output httpsUrl string = 'https://${webApp.properties.defaultHostName}'
output appName string = webApp.name
