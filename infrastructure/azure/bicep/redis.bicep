param location string
param environmentName string

var cacheName = 'redis-${environmentName}-inv'

resource redisCache 'Microsoft.Cache/redis@2024-03-01' = {
  name: cacheName
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisVersion: '6'
  }
}

output hostname string = redisCache.properties.hostName
output primaryKey string = redisCache.listKeys().primaryKey
