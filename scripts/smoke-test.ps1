param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "admin",
    [string]$Password = "admin123",
    [string]$SampleImagePath = (Join-Path $PSScriptRoot "..\demo-assets\sample-white-product.png")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-ApiJson {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers,
        [object]$Body = $null,
        [string]$ContentType = "application/json"
    )

    $params = @{
        Method      = $Method
        Uri         = $Url
        Headers     = $Headers
        ErrorAction = "Stop"
    }

    if ($null -ne $Body) {
        $params["Body"] = if ($ContentType -eq "application/json") { $Body | ConvertTo-Json -Depth 8 } else { $Body }
        $params["ContentType"] = $ContentType
    }

    return Invoke-RestMethod @params
}

Write-Host "1/6 Login..."
$login = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/auth/login" -Headers @{} -Body @{
    username = $Username
    password = $Password
}

$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }

$uploaded = $null
if (Test-Path $SampleImagePath) {
    Write-Host "2/6 Upload sample image..."
    $curlOutput = & curl.exe -sS `
        -H "Authorization: Bearer $token" `
        -F "image=@$SampleImagePath" `
        "$BaseUrl/api/upload/image"
    $uploaded = $curlOutput | ConvertFrom-Json
}
else {
    Write-Host "2/6 Skip image upload because sample image was not found."
}

Write-Host "3/6 Create project..."
$project = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/projects" -Headers $headers -Body @{
    name         = "Smoke Test Project"
    page_type    = "main_image"
    platform     = "taobao"
    product_name = "aluminum material"
}

Write-Host "4/6 Generate version..."
$generation = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/projects/$($project.id)/generate" -Headers $headers -Body @{
    message           = "Create a Taobao main image, highlight corrosion resistance and customization, and keep an industrial clean style."
    source_image_path = $uploaded.file_path
    guide_fields      = @{
        page_type      = "main_image"
        platform       = "taobao"
        product_name   = "aluminum material"
        style_keywords = @("industrial clean", "metal texture")
        selling_points = @("corrosion resistant", "customizable")
    }
}

if ($generation.mode -eq "clarify") {
    Write-Host "Generation returned clarify mode. Questions:"
    $generation.questions | ForEach-Object { Write-Host "- $_" }
    exit 0
}

$versionId = $generation.version.id

Write-Host "5/6 Approve version..."
$null = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/projects/$($project.id)/versions/$versionId/review" -Headers $headers -Body @{
    action  = "approved"
    comment = "Smoke test approved."
}

Write-Host "6/6 Finalize version..."
$finalized = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/api/projects/$($project.id)/versions/$versionId/finalize" -Headers $headers

Write-Host ""
Write-Host "Smoke test completed."
Write-Host "Project ID: $($finalized.id)"
Write-Host "Final Version ID: $($finalized.final_version_id)"
