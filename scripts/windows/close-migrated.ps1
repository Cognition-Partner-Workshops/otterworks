param([int]$Rows = 20000, [string]$BusinessDate = '20261109')
$ErrorActionPreference = 'Stop'
Push-Location (Resolve-Path "$PSScriptRoot/../..")
try {
    $env:PYTHONUTF8 = '1'
    $ErrorActionPreference = 'Continue'
    & ./warehouse/.venv/Scripts/python.exe scripts/windows/billing-close.py migrated --rows $Rows --business-date $BusinessDate
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) { throw "Migrated close failed ($LASTEXITCODE)" }
} finally { Pop-Location }
