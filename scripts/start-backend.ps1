param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$ServeFrontend,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$backendCmd = Join-Path $PSScriptRoot "..\start-backend.cmd"
$arguments = @("--port", $Port.ToString(), "--bind-host", $BindHost)

if ($ServeFrontend) {
    $arguments += "--serve-frontend"
}
if ($NoReload) {
    $arguments += "--no-reload"
}

& $backendCmd @arguments
