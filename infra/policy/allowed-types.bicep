// Azure Policy guard rail for rg-ar-demo: only the resource types used by the demo may be created.
// Uses the built-in policy "Allowed resource types". Policy assignments are free.
//
// Deploy:  az deployment group create -g rg-ar-demo -f infra/policy/allowed-types.bicep

targetScope = 'resourceGroup'

@description('Resource types allowed in this resource group (everything else is denied).')
param allowedResourceTypes array = [
  'Microsoft.OperationalInsights/workspaces'
  'Microsoft.App/managedEnvironments'
  'Microsoft.App/containerApps'
  'Microsoft.DBforPostgreSQL/flexibleServers'
  'Microsoft.DBforPostgreSQL/flexibleServers/databases'
  'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules'
  'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
  'Microsoft.KeyVault/vaults'
  'Microsoft.KeyVault/vaults/secrets'
  'Microsoft.ManagedIdentity/userAssignedIdentities'
  'Microsoft.Authorization/roleAssignments'
]

// Built-in definition "Allowed resource types"
var allowedTypesDefinitionId = tenantResourceId('Microsoft.Authorization/policyDefinitions', 'a08ec900-254a-4555-9bf5-e42af04b5c5c')

resource allowedTypes 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'ar-demo-allowed-resource-types'
  properties: {
    displayName: 'rg-ar-demo: allow only the free-tier demo resource types'
    description: 'Blocks any resource type not used by the AR demo (no ACR, VMs, public IPs, gateways, ...).'
    policyDefinitionId: allowedTypesDefinitionId
    enforcementMode: 'Default'
    parameters: {
      listOfResourceTypesAllowed: {
        value: allowedResourceTypes
      }
    }
  }
}

output assignmentId string = allowedTypes.id
