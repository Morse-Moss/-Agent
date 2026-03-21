param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Join-Path $PSScriptRoot ".."
$frontendDir = Join-Path $projectRoot "frontend"
$backendCmd = Join-Path $projectRoot "start-backend.cmd"

Push-Location $frontendDir
try {
    if (-not (Test-Path "node_modules")) {
        npm.cmd install
    }
    npm.cmd run build
}
finally {
    Pop-Location
}

& $backendCmd --port $Port --bind-host $BindHost --serve-frontend --no-reload
