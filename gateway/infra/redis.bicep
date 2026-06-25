// Azure Managed Redis (redisEnterprise) for APIM semantic caching.
// RediSearch is required for the vector similarity lookup used by
// llm-semantic-cache-lookup. Deployed separately from main.bicep because it is
// the slowest resource to provision.

@description('Region for the cache (match APIM/Foundry).')
param location string = 'eastus2'

@description('Azure Managed Redis resource name.')
param cacheName string = 'aig-acw-cache'

resource cache 'Microsoft.Cache/redisEnterprise@2024-10-01' = {
  name: cacheName
  location: location
  sku: {
    name: 'Balanced_B0'
  }
}

resource db 'Microsoft.Cache/redisEnterprise/databases@2024-10-01' = {
  parent: cache
  name: 'default'
  properties: {
    clientProtocol: 'Encrypted'
    port: 10000
    clusteringPolicy: 'EnterpriseCluster'
    evictionPolicy: 'NoEviction'
    modules: [
      {
        name: 'RediSearch'
      }
    ]
  }
}

output cacheHostName string = cache.properties.hostName
output cachePort int = 10000
