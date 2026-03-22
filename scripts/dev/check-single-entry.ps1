param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootResponse = Invoke-WebRequest -Uri "$BaseUrl/" -Method Get -UseBasicParsing
$createResponse = Invoke-WebRequest -Uri "$BaseUrl/create" -Method Get -UseBasicParsing
$healthResponse = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get

Write-Host "Root status: $($rootResponse.StatusCode)"
Write-Host "Create status: $($createResponse.StatusCode)"
Write-Host "Health status: $($healthResponse.status)"

if ($rootResponse.Content -notmatch "<!doctype html>|<!DOCTYPE html>") {
    throw "Root path did not return the frontend HTML shell."
}

if ($createResponse.Content -notmatch "<!doctype html>|<!DOCTYPE html>") {
    throw "SPA route /create did not return the frontend HTML shell."
}

if ($healthResponse.status -ne "ok") {
    throw "Health endpoint did not return ok."
}

Write-Host "Single-entry check passed."
