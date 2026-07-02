// Direct-access model RBAC lab — APIM (aig-acw) exposing three Foundry models as
// individual OpenAI-compatible APIs, each locked to an Entra app role so you can
// group and limit which developers (or service principals) may call which model.
// Deployed at resource-group scope (rg-foundry).
//
// Access model:
//   - Coding Assistants product  -> Codex API  (gpt-5.3-codex)  -> Model.Coding.Invoke
//   - General LLM product        -> GPT-5.2 API + Mistral API   -> Model.General.Invoke
// Products/subscriptions handle metering + a stable subscription key; the Entra
// app-role check (validate-azure-ad-token) is the real identity boundary.

@description('Name of the existing API Management instance.')
param apimName string = 'aig-acw'

@description('Foundry Azure AI Model Inference base URL (serves gpt-5.2, Mistral-Large-3 via chat/completions).')
param inferenceBaseUrl string = 'https://foundry-acw.services.ai.azure.com/models'

@description('Azure OpenAI v1 base URL for the Responses API (serves gpt-5.3-codex).')
param openaiResponsesBaseUrl string = 'https://foundry-acw.openai.azure.com/openai/v1'

@description('Entra tenant ID used to validate caller tokens.')
param aadTenantId string = '38c1a7b0-f16b-45fd-a528-87d8720e868e'

@description('Audience the caller token must target (the resource app ID URI).')
param modelAudience string = 'api://ef395518-fb4e-4675-9edc-34983ce42ad9'

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimName
}

// NOTE: The APIM system-assigned identity already holds the "Cognitive Services
// User" role on foundry-acw (account keys are disabled). If you redeploy into a
// fresh environment, grant it with:
//   az role assignment create --assignee <apim-principalId> \
//     --role "Cognitive Services User" --scope <foundry-account-id>

// Named values referenced by the per-model policies so tenant/audience are not
// hard-coded in the policy XML.
resource nvTenant 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apim
  name: 'aad-tenant-id'
  properties: {
    displayName: 'aad-tenant-id'
    value: aadTenantId
  }
}

resource nvAudience 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apim
  name: 'model-audience'
  properties: {
    displayName: 'model-audience'
    value: modelAudience
  }
}

// Shared backend routing (MI auth + backend + api-version) used by every API.
resource backendFragment 'Microsoft.ApiManagement/service/policyFragments@2023-09-01-preview' = {
  parent: apim
  name: 'direct-models-backend'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/backend-fragment.xml')
  }
  dependsOn: [ backend ]
}

resource backend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'foundry-models'
  properties: {
    description: 'Foundry Azure AI Model Inference for the direct-access lab (gpt-5.2, Mistral-Large-3 via chat/completions)'
    url: inferenceBaseUrl
    protocol: 'http'
  }
}

// gpt-5.3-codex is a Responses-API model, served by the Azure OpenAI v1
// endpoint rather than the generic model-inference chat/completions route.
resource openaiBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'foundry-openai'
  properties: {
    description: 'Azure OpenAI v1 Responses endpoint for the direct-access lab (gpt-5.3-codex)'
    url: openaiResponsesBaseUrl
    protocol: 'http'
  }
}

resource responsesFragment 'Microsoft.ApiManagement/service/policyFragments@2023-09-01-preview' = {
  parent: apim
  name: 'direct-responses-backend'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/responses-backend-fragment.xml')
  }
  dependsOn: [ openaiBackend ]
}

// ---- Codex API (Coding Assistants) --------------------------------------

resource codexApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'model-codex'
  properties: {
    displayName: 'Model — gpt-5.3-codex (Coding)'
    description: 'Direct Azure OpenAI Responses API locked to gpt-5.3-codex. Requires the Model.Coding.Invoke app role. POST /codex/responses with {"input": "..."}.'
    path: 'codex'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource codexOp 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: codexApi
  name: 'responses'
  properties: {
    displayName: 'Responses'
    method: 'POST'
    urlTemplate: '/responses'
    description: 'Azure OpenAI Responses API. Send {"input": "..."}; the model field is forced to gpt-5.3-codex by policy.'
  }
}

resource codexPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: codexApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/codex.xml')
  }
  dependsOn: [ openaiBackend, responsesFragment, nvTenant, nvAudience, codexOp ]
}

// ---- GPT-5.2 API (General LLM) ------------------------------------------

resource gpt52Api 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'model-gpt52'
  properties: {
    displayName: 'Model — gpt-5.2 (General)'
    description: 'Direct OpenAI-compatible chat completions locked to gpt-5.2. Requires the Model.General.Invoke app role.'
    path: 'gpt52'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource gpt52Op 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: gpt52Api
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions. The model field is forced to gpt-5.2 by policy.'
  }
}

resource gpt52Policy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: gpt52Api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/gpt52.xml')
  }
  dependsOn: [ backend, backendFragment, nvTenant, nvAudience, gpt52Op ]
}

// ---- Mistral API (General LLM) ------------------------------------------

resource mistralApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'model-mistral'
  properties: {
    displayName: 'Model — Mistral-Large-3 (General)'
    description: 'Direct OpenAI-compatible chat completions locked to Mistral-Large-3. Requires the Model.General.Invoke app role.'
    path: 'mistral'
    protocols: [ 'https' ]
    subscriptionRequired: true
  }
}

resource mistralOp 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: mistralApi
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/chat/completions'
    description: 'OpenAI chat completions. The model field is forced to Mistral-Large-3 by policy.'
  }
}

resource mistralPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: mistralApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/mistral.xml')
  }
  dependsOn: [ backend, backendFragment, nvTenant, nvAudience, mistralOp ]
}

// ---- Products (access bundles) ------------------------------------------

resource codingProduct 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apim
  name: 'coding-assistants'
  properties: {
    displayName: 'Coding Assistants'
    description: 'Coding-assistant models (gpt-5.3-codex). Callers still need the Model.Coding.Invoke Entra app role.'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

resource generalProduct 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apim
  name: 'general-llm'
  properties: {
    displayName: 'General LLM'
    description: 'General-purpose models (gpt-5.2, Mistral-Large-3). Callers still need the Model.General.Invoke Entra app role.'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

resource codingProductCodex 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: codingProduct
  name: codexApi.name
}

resource generalProductGpt52  'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: generalProduct
  name: gpt52Api.name
}

resource generalProductMistral 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: generalProduct
  name: mistralApi.name
}

// ---- Subscriptions (admin-provisioned; metering + stable key) -----------

resource codingSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' = {
  parent: apim
  name: 'coding-assistants-demo'
  properties: {
    displayName: 'Coding Assistants demo client'
    scope: codingProduct.id
    state: 'active'
  }
}

resource generalSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' = {
  parent: apim
  name: 'general-llm-demo'
  properties: {
    displayName: 'General LLM demo client'
    scope: generalProduct.id
    state: 'active'
  }
}

output codexApiUrl string = '${apim.properties.gatewayUrl}/codex/responses'
output gpt52ApiUrl string = '${apim.properties.gatewayUrl}/gpt52/chat/completions'
output mistralApiUrl string = '${apim.properties.gatewayUrl}/mistral/chat/completions'
