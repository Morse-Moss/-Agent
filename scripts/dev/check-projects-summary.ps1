param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

$login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" -ContentType "application/json" -Body (@{
    username = "admin"
    password = "admin123"
} | ConvertTo-Json)

$headers = @{
    Authorization = "Bearer $($login.access_token)"
}

$rawProjects = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/projects" -Headers $headers
$projects = if ($rawProjects -is [System.Array]) { $rawProjects } elseif ($null -eq $rawProjects) { @() } else { @($rawProjects) }
$requiredFields = @("cover_asset_path", "cover_asset_type", "cover_width", "cover_height", "latest_version_no")

if ($projects.Count -eq 0) {
    Write-Host "Projects API returned an empty list. Endpoint is reachable, but there are no rows to inspect."
    exit 0
}

foreach ($project in $projects) {
    $propertyNames = @($project.PSObject.Properties.Name)
    $missing = @($requiredFields | Where-Object { $_ -notin $propertyNames })
    if ($missing.Count -gt 0) {
        throw "Project $($project.id) is missing fields: $($missing -join ', ')"
    }
}

Write-Host "Validated $($projects.Count) project rows. Cover summary fields are present on every row."
