// Storyteller AI Gateway lab — APIM (aig-acw) fronting the Foundry Azure AI
// Model Inference endpoint. Deployed at resource-group scope (rg-foundry).
//
// Stage 1: managed-identity role assignment, backend, API + operation, and the
// base passthrough policy. Later stages layer on the AI gateway policies
// (token limit, token metrics, semantic cache, content safety, custom).

@description('Name of the existing API Management instance.')
param apimName string = 'aig-acw'

@description('Name of the existing Foundry (AIServices) account.')
param foundryName string = 'foundry-acw'

@description('Foundry Azure AI Model Inference base URL (serves all models).')
param inferenceBaseUrl string = 'https://foundry-acw.services.ai.azure.com/models'

@description('Azure AI Content Safety endpoint (reuses the foundry-acw account).')
param contentSafetyUrl string = 'https://foundry-acw.cognitiveservices.azure.com'

@description('API path suffix exposed by the gateway.')
param apiPath string = 'storyteller'

@description('Resource ID of the existing Application Insights component to reuse.')
param appInsightsId string = '/subscriptions/80e91cef-e379-45a7-b8bf-ebfffea647da/resourceGroups/rg-foundry/providers/microsoft.insights/components/proj-acw-appinsights-4422'

@description('Instrumentation key of the existing Application Insights component.')
@secure()
param appInsightsInstrumentationKey string

@description('Log Analytics workspace (backing the reused App Insights) for AI gateway LLM logs.')
param logAnalyticsWorkspaceId string = '/subscriptions/80e91cef-e379-45a7-b8bf-ebfffea647da/resourceGroups/rg-foundry/providers/Microsoft.OperationalInsights/workspaces/DefaultWorkspace-3bb77f17-980b-4c5c-abc9-f34a53718e65'

@description('Embeddings API URL (no query params) used for semantic cache vectors.')
param embeddingsUrl string = 'https://foundry-acw.openai.azure.com/openai/deployments/text-embedding-3-small/embeddings'

@description('Azure Managed Redis host name for the external cache. Empty = skip semantic cache wiring.')
param redisHostName string = ''

@description('Azure Managed Redis access key.')
@secure()
param redisAccessKey string = ''

@description('Azure Managed Redis SSL port.')
param redisPort int = 10000

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimName
}

// Reusable backend routing (MI auth + backend + api-version) shared by every
// Storyteller API via include-fragment.
resource backendFragment 'Microsoft.ApiManagement/service/policyFragments@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-backend'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/backend-fragment.xml')
  }
}

// NOTE: The APIM system-assigned identity already holds the "Cognitive Services
// User" role on foundry-acw (required because account keys are disabled). That
// assignment is managed outside this template; if you redeploy into a fresh
// environment, grant it with:
//   az role assignment create --assignee <apim-principalId> \
//     --role "Cognitive Services User" --scope <foundry-account-id>

resource backend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'foundry-inference'
  properties: {
    description: 'Foundry Azure AI Model Inference (gpt-5.2, DeepSeek, Mistral)'
    url: inferenceBaseUrl
    protocol: 'http'
  }
}

// Azure AI Content Safety backend — reuses the foundry-acw content-safety
// endpoint. Backend-level managed identity (the APIM MI already holds Cognitive
// Services User on foundry-acw) authenticates the screening calls.
resource contentSafetyBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'content-safety'
  properties: {
    description: 'Azure AI Content Safety (foundry-acw)'
    url: contentSafetyUrl
    protocol: 'http'
    credentials: {
      managedIdentity: {
        resource: 'https://cognitiveservices.azure.com'
      }
    }
  }
}

// Embeddings backend — used by llm-semantic-cache-lookup to vectorize prompts.
resource embeddingsBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'embeddings-backend'
  properties: {
    description: 'text-embedding-3-small (foundry-acw) for semantic cache vectors'
    url: embeddingsUrl
    protocol: 'http'
    credentials: {
      managedIdentity: {
        resource: 'https://cognitiveservices.azure.com'
      }
    }
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-llm'
  properties: {
    displayName: 'Storyteller LLM (Foundry)'
    description: 'OpenAI-compatible chat completions for the storyteller models, governed by the AI gateway.'
    path: apiPath
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource chatCompletions 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: api
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions. Body must include a "model" field (e.g. gpt-5.2, DeepSeek-V3.2, Mistral-Large-3).'
  }
}

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/base.xml')
  }
  dependsOn: [ backend, backendFragment, apiDiagnostic ]
}

// Throttled variant — same backend, adds llm-token-limit for the rate-limit demo.
resource throttledApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-llm-throttled'
  properties: {
    displayName: 'Storyteller LLM (token-limited)'
    description: 'Same Foundry backend with a low per-subscription token rate limit, for the llm-token-limit demo.'
    path: '${apiPath}-throttled'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource throttledChatCompletions 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: throttledApi
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions, token-rate-limited.'
  }
}

resource throttledApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: throttledApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/token-limit.xml')
  }
  dependsOn: [ backend, backendFragment ]
}

// Content-safety variant — same backend, screens prompts via Azure AI Content Safety.
resource safetyApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-llm-safety'
  properties: {
    displayName: 'Storyteller LLM (content-safety)'
    description: 'Same Foundry backend with Azure AI Content Safety screening, for the llm-content-safety demo.'
    path: '${apiPath}-safety'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource safetyChatCompletions 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: safetyApi
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions, content-safety screened.'
  }
}

resource safetyApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: safetyApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/content-safety.xml')
  }
  dependsOn: [ backend, backendFragment, contentSafetyBackend ]
}

// Semantic-cache variant — same backend, adds vector cache lookup/store.
resource cacheApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-llm-cache'
  properties: {
    displayName: 'Storyteller LLM (semantic cache)'
    description: 'Same Foundry backend with semantic caching, for the llm-semantic-cache demo.'
    path: '${apiPath}-cache'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource cacheChatCompletions 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: cacheApi
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions, semantically cached.'
  }
}

resource cacheApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: cacheApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/semantic-cache.xml')
  }
  dependsOn: [ backend, backendFragment, embeddingsBackend ]
}

// Custom-policy variant — same backend, adds a model allow-list + governance
// headers via plain C# policy expressions (extensibility beyond the llm-* set).
resource customApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-llm-custom'
  properties: {
    displayName: 'Storyteller LLM (custom policy)'
    description: 'Same Foundry backend with a custom model allow-list and governance response headers.'
    path: '${apiPath}-custom'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource customChatCompletions 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: customApi
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions, model-allow-listed with governance headers.'
  }
}

resource customApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: customApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/custom-policy.xml')
  }
  dependsOn: [ backend, backendFragment ]
}

// External Redis cache binding — only created once Redis host/key are supplied.
resource externalCache 'Microsoft.ApiManagement/service/caches@2023-09-01-preview' = if (!empty(redisHostName)) {
  parent: apim
  name: 'default'
  properties: {
    description: 'Azure Managed Redis (RediSearch) for semantic caching'
    connectionString: '${redisHostName}:${redisPort},password=${redisAccessKey},ssl=True,abortConnect=False'
    useFromLocation: 'default'
  }
}

// Dedicated product + subscription so demo clients have a stable subscription key.
resource product 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller'
  properties: {
    displayName: 'Storyteller Lab'
    description: 'AI gateway lab product fronting the Foundry storyteller models.'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

resource productApi 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: product
  name: api.name
}

resource productThrottledApi 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: product
  name: throttledApi.name
}

resource productSafetyApi 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: product
  name: safetyApi.name
}

resource productCacheApi 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: product
  name: cacheApi.name
}

resource productCustomApi 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: product
  name: customApi.name
}

resource subscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-demo'
  properties: {
    displayName: 'Storyteller demo client'
    scope: product.id
    state: 'active'
  }
}

// Application Insights logger (reuses the existing proj-acw-appinsights-4422).
resource aiLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = {
  parent: apim
  name: 'appinsights'
  properties: {
    loggerType: 'applicationInsights'
    description: 'Reused proj-acw-appinsights-4422 for LLM token metrics + logging'
    resourceId: appInsightsId
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
  }
}

// Diagnostic on the main API; metrics:true is required for llm-emit-token-metric
// custom metrics. The largeLanguageModel block logs the actual prompts and
// completions (as App Insights trace dependencies) for the LLM logging demo.
resource apiDiagnostic 'Microsoft.ApiManagement/service/apis/diagnostics@2024-10-01-preview' = {
  parent: api
  name: 'applicationinsights'
  properties: {
    loggerId: aiLogger.id
    alwaysLog: 'allErrors'
    metrics: true
    largeLanguageModel: {
      logs: 'enabled'
      requests: {
        messages: 'all'
        maxSizeInBytes: 32768
      }
      responses: {
        messages: 'all'
        maxSizeInBytes: 32768
      }
    }
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    verbosity: 'information'
    logClientIp: true
    httpCorrelationProtocol: 'W3C'
  }
}

// Azure Monitor diagnostic setting on the APIM service — routes the AI gateway
// LLM logs (prompts + completions captured by the largeLanguageModel diagnostic
// above) to the Log Analytics workspace, where they land in the
// ApiManagementGatewayLlmLog table for the logging demo.
resource gatewayLlmDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'aig-llm-logs'
  scope: apim
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    // 'Dedicated' routes records to the resource-specific
    // ApiManagementGatewayLlmLog table. The default ('AzureDiagnostics')
    // would instead dump them into the legacy, schema-less AzureDiagnostics
    // table, where the logging demo's KQL would not find them.
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        category: 'GatewayLlmLogs'
        enabled: true
      }
    ]
  }
}

output gatewayApiUrl string = '${apim.properties.gatewayUrl}/${apiPath}'
output apimPrincipalId string = apim.identity.principalId
