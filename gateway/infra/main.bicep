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

@description('API path suffix exposed by the gateway.')
param apiPath string = 'storyteller'

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
  dependsOn: [ backend, backendFragment ]
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

resource subscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' = {
  parent: apim
  name: 'storyteller-demo'
  properties: {
    displayName: 'Storyteller demo client'
    scope: product.id
    state: 'active'
  }
}

output gatewayApiUrl string = '${apim.properties.gatewayUrl}/${apiPath}'
output apimPrincipalId string = apim.identity.principalId
