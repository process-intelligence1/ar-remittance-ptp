// AR Remittance demo environment - everything in resource group rg-ar-demo.
// ZERO COST: free-tier / consumption SKUs only. See docs/DAY3_GUIDE.md.
//
// Deploy (from the repo root, see the guide for the full command):
//   az deployment group create -g rg-ar-demo -f infra/main.bicep -p infra/main.parameters.json -p pgAdminPassword=... adminPrincipalId=...
//
// Two passes on the very first deployment:
//   1) deployApp=false  -> creates everything except the Container App
//   2) the owner stores the GHCR pull token in Key Vault (secret "ghcr-pull-token")
//   3) deployApp=true   -> creates the Container App, which reads both secrets from Key Vault

@description('Azure region; defaults to the resource group region.')
param location string = resourceGroup().location

@description('PostgreSQL administrator login name.')
param pgAdminLogin string = 'aradmin'

@secure()
@description('PostgreSQL administrator password. Generated at deploy time; never stored in a file.')
param pgAdminPassword string

@description('Public IP of the owner laptop allowed through the PostgreSQL firewall. Empty = no rule.')
param clientIp string = ''

@description('Object id of the owner (Entra user) who may read/write Key Vault secrets. Empty = none.')
param adminPrincipalId string = ''

@description('Create the Container App (false on the very first pass, before the GHCR token is in Key Vault).')
param deployApp bool = true

@description('Container image to run. The GitHub workflow later switches it to the commit-SHA tag.')
param containerImage string = 'ghcr.io/process-intelligence1/ar-api:latest'

@description('GitHub user that owns the GHCR pull token.')
param ghcrUsername string = 'process-intelligence1'

@description('Front-end origins allowed to call the API (comma separated).')
param corsOrigins string = 'http://localhost:5173'

@description('Demo business date used by all rules.')
param businessDate string = '2026-10-28'

var tags = {
  project: 'ar-demo'
  cost: 'free-tier'
}
var suffix = uniqueString(resourceGroup().id)
var kvSecretsUserRole = '4633458b-17de-408a-b874-0445c86b69e6'
var kvSecretsOfficerRole = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

// ---------------------------------------------------------------------------
// Logs: Log Analytics with a hard daily cap (0.1 GB/day, far below the 5 GB/month free allowance)
// ---------------------------------------------------------------------------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-ar-demo'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: json('0.1')
    }
  }
}

// ---------------------------------------------------------------------------
// Container Apps environment - Consumption plan only (no workload profiles)
// ---------------------------------------------------------------------------
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-ar-demo'
  location: location
  tags: tags
  properties: {
    zoneRedundant: false
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------
// PostgreSQL Flexible Server - Burstable B1ms, 32 GB (free for 12 months on a free account)
// ---------------------------------------------------------------------------
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'psql-ar-demo-${suffix}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '17'
    administratorLogin: pgAdminLogin
    administratorLoginPassword: pgAdminPassword
    storage: {
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: 'ar_demo'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// 0.0.0.0 - 0.0.0.0 is Azure's special rule for "allow Azure services" (the Container App)
resource pgFwAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: pg
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource pgFwClient 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (!empty(clientIp)) {
  parent: pg
  name: 'OwnerLaptop'
  properties: {
    startIpAddress: clientIp
    endIpAddress: clientIp
  }
}

// ---------------------------------------------------------------------------
// Key Vault (RBAC mode, Standard) holding DATABASE_URL and the GHCR pull token
// ---------------------------------------------------------------------------
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-ardemo-${suffix}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource dbUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'database-url'
  tags: tags
  properties: {
    value: 'postgresql+psycopg://${pgAdminLogin}:${pgAdminPassword}@${pg.properties.fullyQualifiedDomainName}:5432/${pgDb.name}?sslmode=require'
  }
}

// Identity created BEFORE the app, so the app can read Key Vault while it is being created
resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-ar-api'
  location: location
  tags: tags
}

resource apiIdentityKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, apiIdentity.id, kvSecretsUserRole)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRole)
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource ownerKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminPrincipalId)) {
  scope: kv
  name: guid(kv.id, adminPrincipalId, kvSecretsOfficerRole)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsOfficerRole)
    principalId: adminPrincipalId
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------
// Container App "ar-api": scale to zero, max 1 replica, 0.25 vCPU / 0.5 GiB
// ---------------------------------------------------------------------------
resource app 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: 'ar-api'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned,UserAssigned'
    userAssignedIdentities: {
      '${apiIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/database-url'
          identity: apiIdentity.id
        }
        {
          name: 'ghcr-pull-token'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/ghcr-pull-token'
          identity: apiIdentity.id
        }
      ]
      registries: [
        {
          server: 'ghcr.io'
          username: ghcrUsername
          passwordSecretRef: 'ghcr-pull-token'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ar-api'
          image: containerImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'ENVIRONMENT'
              value: 'demo'
            }
            {
              name: 'BUSINESS_DATE'
              value: businessDate
            }
            {
              name: 'CORS_ORIGINS'
              value: corsOrigins
            }
            {
              name: 'OUTBOUND_MODE'
              value: 'redirect'
            }
            {
              name: 'OUTBOUND_REDIRECT_TO'
              value: 'processintelligence1@gmail.com'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    apiIdentityKv
    dbUrlSecret
  ]
}

// The app's own system-assigned identity also gets read access (for later use, e.g. Blob/Key Vault from code)
resource appSystemKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployApp) {
  scope: kv
  name: guid(kv.id, 'ar-api-system', kvSecretsUserRole)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRole)
    principalId: app!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output keyVaultName string = kv.name
output postgresServerName string = pg.name
output postgresFqdn string = pg.properties.fullyQualifiedDomainName
output apiUrl string = deployApp ? 'https://${app!.properties.configuration.ingress.fqdn}' : ''
