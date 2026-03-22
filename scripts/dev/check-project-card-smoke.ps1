$ErrorActionPreference = "Stop"

$projectsPage = Get-Content -Path "g:\demo2\frontend\src\pages\ProjectsPage.tsx" -Raw
$createPage = Get-Content -Path "g:\demo2\frontend\src\pages\CreatePage.tsx" -Raw
$styles = Get-Content -Path "g:\demo2\frontend\src\main.css" -Raw

$checks = @(
    @{
        Name = "projects page uses cover_asset_path"
        Passed = $projectsPage -match "project\.cover_asset_path"
    },
    @{
        Name = "projects page includes placeholder state"
        Passed = $projectsPage -match "project-cover-placeholder"
    },
    @{
        Name = "create page includes version thumbnail block"
        Passed = $createPage -match "version-thumb"
    },
    @{
        Name = "cover image style exists"
        Passed = $styles -match "\.project-cover-image"
    },
    @{
        Name = "cover placeholder style exists"
        Passed = $styles -match "\.project-cover-placeholder"
    }
)

$failed = @($checks | Where-Object { -not $_.Passed })
if ($failed.Count -gt 0) {
    throw "Smoke checks failed: $($failed.Name -join ' / ')"
}

Write-Host "Frontend smoke checks passed for project cards and workbench thumbnails."
