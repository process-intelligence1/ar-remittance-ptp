// AR Remittance demo environment - everything in resource group rg-ar-demo.
// ZERO COST: free-tier / consumption SKUs only. See docs/DAY3_GUIDE.md.
//
// Deploy (from the repo root, see the guide for the full command):
//   az deployment group create -g rg-ar-demo -f infra/main.bicep -p infra/main.parameters.json -p pgAdminPassword=... adminPrincipalId=...
//
// Two passes on the very first deployment:
//   1) deployApp=false  -> creates everything except the Container App
//   2) the owner stores the app secrets in Key Vault (gmail-token, admin-api-key; database-url is written here)
//   3) deployApp=true   -> creates the Container App, which reads its secrets from Key Vault
// The image (ghcr.io/process-intelligence1/ar-api) is PUBLIC, so pulling it needs no registry credentials.

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

@description('Create the Container App (false on the very first pass, before the app secrets are in Key Vault).')
param deployApp bool = true

@description('Image tag = the commit SHA that is deployed (never :latest). infra/deploy.ps1 passes the tag the API runs now, so a template deploy never changes the code version; the GitHub workflow moves it forward.')
param imageTag string

// Two images from one Dockerfile: ar-api = slim (no OCR libraries) for the API and the migration job,
// ar-worker = full (Tesseract, OpenCV, ...) for the worker job.
var apiImage = 'ghcr.io/process-intelligence1/ar-api:${imageTag}'
var workerImage = 'ghcr.io/process-intelligence1/ar-worker:${imageTag}'

@description('Front-end origins allowed to call the API (comma separated): ONLY the Static Web App origin (added in M08) and localhost.')
param corsOrigins string = 'http://localhost:5173'

@description('Demo business date used by all rules.')
param businessDate string = '2026-10-28'

@description('Cron schedule (UTC) of the worker job. Every 10 minutes keeps half of the monthly free grant (5 minutes would use ~91 %); see docs/modules/M06_pipeline.md.')
param workerCron string = '*/10 * * * *'

var workerJobName = 'ar-worker'
var tags = {
  project: 'ar-demo'
  cost: 'free-tier'
}
var suffix = uniqueString(resourceGroup().id)
var kvSecretsUserRole = '4633458b-17de-408a-b874-0445c86b69e6'
var kvSecretsOfficerRole = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
var blobDataContributorRole = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

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
// Key Vault (RBAC mode, Standard) holding DATABASE_URL and the app secrets
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

// ---------------------------------------------------------------------------
// Blob storage for raw e-mails and attachments (M01). Standard_LRS, Hot, no public access,
// account keys disabled: only managed identities with a data role can read/write.
// ---------------------------------------------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stardemo${suffix}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Enabled'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource filesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'ar-files'
  properties: {
    publicAccess: 'None'
  }
}

resource apiIdentityBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, apiIdentity.id, blobDataContributorRole)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRole)
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

// Settings the API and the worker job share (the worker is the same image with another command)
var commonEnv = [
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
  {
    name: 'GMAIL_TOKEN_JSON'
    secretRef: 'gmail-token'
  }
  {
    name: 'STORAGE_BACKEND'
    value: 'azure_blob'
  }
  {
    name: 'AZURE_STORAGE_ACCOUNT_URL'
    value: storage.properties.primaryEndpoints.blob
  }
  {
    name: 'AZURE_STORAGE_CONTAINER'
    value: filesContainer.name
  }
  {
    name: 'AZURE_CLIENT_ID'
    value: apiIdentity.properties.clientId
  }
  {
    // the laptop and Azure share one inbox: only Azure polls
    name: 'POLLER_ENABLED'
    value: 'true'
  }
]

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
          // uploaded by the owner (M01); the app cannot start until it exists
          name: 'gmail-token'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/gmail-token'
          identity: apiIdentity.id
        }
        {
          // random key for /api/admin/* (header X-Admin-Key); must exist before deploying
          name: 'admin-api-key'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/admin-api-key'
          identity: apiIdentity.id
        }
        {
          // demo login (M07): the access code presenters type; must exist before deploying
          name: 'demo-access-code'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/demo-access-code'
          identity: apiIdentity.id
        }
        {
          // demo login (M07): random signing key for tokens and signed download links; must exist before deploying
          name: 'jwt-secret'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/jwt-secret'
          identity: apiIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ar-api'
          image: apiImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat(commonEnv, [
            {
              name: 'ADMIN_API_KEY'
              secretRef: 'admin-api-key'
            }
            {
              name: 'DEMO_ACCESS_CODE'
              secretRef: 'demo-access-code'
            }
            {
              name: 'JWT_SECRET'
              secretRef: 'jwt-secret'
            }
            {
              // "Process now" starts the worker job through the Azure management API (see workerStarterRole)
              name: 'AZURE_SUBSCRIPTION_ID'
              value: subscription().subscriptionId
            }
            {
              name: 'AZURE_RESOURCE_GROUP'
              value: resourceGroup().name
            }
            {
              name: 'WORKER_JOB_NAME'
              value: workerJobName
            }
          ])
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
    apiIdentityBlob
    dbUrlSecret
  ]
}

// ---------------------------------------------------------------------------
// Container Apps JOB "ar-worker" (M06): the same image, `python -m app.worker --once`, on a schedule.
// It reads Gmail, then runs read -> classify -> extract -> match for every waiting e-mail.
// 0.5 vCPU / 1 GiB, one run at a time, no job-level retries (retries are kept in the ar.job table).
// ---------------------------------------------------------------------------
resource workerJob 'Microsoft.App/jobs@2024-03-01' = if (deployApp) {
  name: workerJobName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentity.id}': {}
    }
  }
  properties: {
    environmentId: cae.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 600
      replicaRetryLimit: 0
      scheduleTriggerConfig: {
        cronExpression: workerCron
        parallelism: 1
        replicaCompletionCount: 1
      }
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/database-url'
          identity: apiIdentity.id
        }
        {
          name: 'gmail-token'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/gmail-token'
          identity: apiIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ar-worker'
          image: workerImage
          command: [ 'python', '-m', 'app.worker' ]
          args: [ '--once' ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: commonEnv
        }
      ]
    }
  }
  dependsOn: [
    apiIdentityKv
    apiIdentityBlob
    dbUrlSecret
  ]
}

// ---------------------------------------------------------------------------
// Container Apps JOB "ar-migrate": runs the database migrations (alembic upgrade head) once per deploy, INSIDE Azure,
// so the API no longer migrates at start-up (faster cold start) and the database firewall stays closed to GitHub.
// Manual trigger only (the deploy workflow starts it before the new API revision); same image, identity and database secret.
// ---------------------------------------------------------------------------
resource migrateJob 'Microsoft.App/jobs@2024-03-01' = if (deployApp) {
  name: 'ar-migrate'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentity.id}': {}
    }
  }
  properties: {
    environmentId: cae.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/database-url'
          identity: apiIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ar-migrate'
          image: apiImage
          command: [ 'alembic', 'upgrade', 'head' ]
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
          ]
        }
      ]
    }
  }
  dependsOn: [
    apiIdentityKv
    dbUrlSecret
  ]
}

// "Process now" (POST /api/admin/process-now) starts the job right away. The API's identity gets a custom
// role that contains ONE action - start a job - and the role is assigned on the job resource only
// (not on the resource group), so it can start nothing else and read nothing.
resource workerStarterRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'ar-worker-job-starter')
  properties: {
    roleName: 'AR Worker Job Starter (${resourceGroup().name})'
    description: 'Can start executions of Container Apps Jobs, nothing else.'
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.App/jobs/start/action'
        ]
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
    assignableScopes: [
      resourceGroup().id
    ]
  }
}

resource apiStartsWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployApp) {
  scope: workerJob
  name: guid(workerJob.id, apiIdentity.id, workerStarterRole.id)
  properties: {
    roleDefinitionId: workerStarterRole.id
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
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
output storageAccountName string = storage.name
output postgresServerName string = pg.name
output postgresFqdn string = pg.properties.fullyQualifiedDomainName
output migrateJobName string = deployApp ? migrateJob.name : ''
output workerJobName string = deployApp ? workerJob.name : ''
output apiUrl string = deployApp ? 'https://${app!.properties.configuration.ingress.fqdn}' : ''
