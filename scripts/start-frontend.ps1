$ErrorActionPreference = "Stop"
$frontendDir = Join-Path $PSScriptRoot "..\frontend"

Push-Location $frontendDir
try {
    if (-not (Test-Path "node_modules")) {
        npm.cmd install
    }
    npm.cmd run dev
}
finally {
    Pop-Location
}
