<#
Deploy (or preview) the AR demo infrastructure in rg-ar-demo.

  .\infra\deploy.ps1 -WhatIf                 # preview only, changes nothing
  .\infra\deploy.ps1 -SkipApp                # first pass: everything except the Container App
  .\infra\deploy.ps1                         # full deployment incl. the Container App
  .\infra\deploy.ps1 -NoClientIp             # same, without the laptop firewall rule

A new random PostgreSQL password is generated on every run. It only lives in this
PowerShell process and goes straight to Azure (server + Key Vault secret "database-url").
It is never printed or written to a file. After a real run the API is restarted so it
picks up the new DATABASE_URL from Key Vault.
#>
param(
    [switch]$WhatIf,
    [switch]$SkipApp,
    [switch]$NoClientIp,
    [switch]$PolicyOnly
)
$ErrorActionPreference = "Stop"
$rg = "rg-ar-demo"
$root = Split-Path -Parent $PSScriptRoot
$verb = if ($WhatIf) { "what-if" } else { "create" }
$quiet = if ($WhatIf) { @() } else { @("--output", "none") }   # what-if shows its preview; a real run stays quiet

# --- Policy guard rail (allowed resource types) ---
Write-Host "== Policy: allowed resource types ($verb) =="
az deployment group $verb -g $rg -n ar-demo-policy -f "$root\infra\policy\allowed-types.bicep" --only-show-errors @quiet
if ($LASTEXITCODE -ne 0) { throw "Policy deployment failed" }
if ($PolicyOnly) { return }

# --- Inputs that are not secret ---
$adminId = az ad signed-in-user show --query id -o tsv
$clientIp = ""
if (-not $NoClientIp) { $clientIp = (Invoke-RestMethod -Uri "https://api.ipify.org").Trim() }
$deployApp = if ($SkipApp) { "false" } else { "true" }

# --- Secret: strong random password (letters + digits only, so it is URL-safe) ---
$chars = [char[]]"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$pw = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })

Write-Host "== Main infrastructure ($verb, deployApp=$deployApp, laptop IP rule=$(-not $NoClientIp)) =="
az deployment group $verb -g $rg -n ar-demo-main -f "$root\infra\main.bicep" `
    -p "@$root\infra\main.parameters.json" `
    -p pgAdminPassword=$pw adminPrincipalId=$adminId clientIp=$clientIp deployApp=$deployApp `
    --only-show-errors @quiet
$ok = $LASTEXITCODE -eq 0
Remove-Variable pw
if (-not $ok) { throw "Main deployment failed" }

if (-not $WhatIf) {
    az deployment group show -g $rg -n ar-demo-main --query properties.outputs -o jsonc
    if (-not $SkipApp) {
        # Restart so the app reads the new DATABASE_URL from Key Vault
        $rev = az containerapp revision list -n ar-api -g $rg --query "[?properties.active].name | [0]" -o tsv --only-show-errors
        if ($rev) { az containerapp revision restart -n ar-api -g $rg --revision $rev --only-show-errors -o none }
    }
}
