// Azure Managed Redis (redisEnterprise) for APIM semantic caching.
// RediSearch is required for the vector similarity lookup used by
// llm-semantic-cache-lookup. Deployed separately from main.bicep because it is
// the slowest resource to provision.
//
// NOTE on region: Balanced_B0 is a real, current SKU (~$0.02/hr) but is subject
// to per-region capacity. As of this lab, eastus2/eastus/centralus returned
// allocation failures while westus2/westus3 had capacity, so the cache lives in
// westus2 even though APIM is in eastus2. The cross-region hop adds a few ms to
// each cache lookup — negligible for a demo. If your target region has B0
// capacity, set location to match APIM for lowest latency.

@description('Region for the cache. Must have Balanced_B0 capacity.')
param location string = 'westus2'

@description('Azure Managed Redis resource name.')
param cacheName string = 'aig-acw-cache-wus2'

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
