param(
    [switch]$Diagnose,
    [switch]$UsePrivateCredentials,
    [string[]]$Regions = @('VN'),
    [int]$Port = 5055
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$credentialPath = Join-Path $projectRoot '.private\credentials.dpapi'
$previousValues = @{}
try {
    if ($UsePrivateCredentials -and (Test-Path -LiteralPath $credentialPath)) {
        $secure = Get-Content -Raw -LiteralPath $credentialPath | ConvertTo-SecureString
        $plain = [System.Net.NetworkCredential]::new('', $secure).Password
        $pairs = $plain | ConvertFrom-Json
        foreach ($property in $pairs.PSObject.Properties) {
            if ($property.Name -notmatch '^FREEFIRE_[A-Z]+_(UID|PASSWORD)$') {
                throw 'Unexpected key in private credential configuration.'
            }
            $previousValues[$property.Name] = [Environment]::GetEnvironmentVariable($property.Name, 'Process')
            [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process')
        }
        $plain = $null
        $pairs = $null
    }
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if ($Diagnose) {
        & $python 'tools/diagnose.py' --regions @Regions
    } else {
        & $python -m flask --app app run --host 127.0.0.1 --port $Port --no-debugger --no-reload
    }
    $resultCode = $LASTEXITCODE
} finally {
    foreach ($name in $previousValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process')
    }
}
exit $resultCode
