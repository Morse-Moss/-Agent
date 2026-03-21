param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\demo-assets")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

function Save-Png {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [string]$Path
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $Bitmap.Dispose()
}

$null = New-Item -ItemType Directory -Force -Path $OutputDir

$productBitmap = New-Object System.Drawing.Bitmap 1200, 1200
$graphics = [System.Drawing.Graphics]::FromImage($productBitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::White)

$shadowBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(26, 0, 0, 0))
$bodyBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(233, 237, 241))
$strokePen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(118, 128, 140), 6)
$accentBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(52, 66, 80))
$font = New-Object System.Drawing.Font("Microsoft YaHei", 42, [System.Drawing.FontStyle]::Bold)

$graphics.FillEllipse($shadowBrush, 250, 850, 700, 180)
$graphics.FillRectangle($bodyBrush, 320, 250, 560, 520)
$graphics.DrawRectangle($strokePen, 320, 250, 560, 520)
$graphics.FillRectangle($accentBrush, 380, 330, 440, 74)
$graphics.DrawString("ALU DEMO", $font, [System.Drawing.Brushes]::White, 420, 338)
$graphics.FillRectangle($accentBrush, 470, 450, 260, 190)
$graphics.Dispose()
$shadowBrush.Dispose()
$bodyBrush.Dispose()
$strokePen.Dispose()
$accentBrush.Dispose()
$font.Dispose()

Save-Png -Bitmap $productBitmap -Path (Join-Path $OutputDir "sample-white-product.png")

$tallBitmap = New-Object System.Drawing.Bitmap 1200, 1200
$graphics2 = [System.Drawing.Graphics]::FromImage($tallBitmap)
$graphics2.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics2.Clear([System.Drawing.Color]::White)
$bodyBrush2 = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(223, 229, 235))
$strokePen2 = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(126, 138, 152), 6)
$accentBrush2 = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(37, 54, 72))
$font2 = New-Object System.Drawing.Font("Microsoft YaHei", 38, [System.Drawing.FontStyle]::Bold)

$graphics2.FillRectangle($bodyBrush2, 430, 180, 340, 720)
$graphics2.DrawRectangle($strokePen2, 430, 180, 340, 720)
$graphics2.FillRectangle($accentBrush2, 482, 270, 236, 80)
$graphics2.DrawString("CUTOUT", $font2, [System.Drawing.Brushes]::White, 505, 286)
$graphics2.FillRectangle($accentBrush2, 510, 430, 180, 300)
$graphics2.Dispose()
$bodyBrush2.Dispose()
$strokePen2.Dispose()
$accentBrush2.Dispose()
$font2.Dispose()

Save-Png -Bitmap $tallBitmap -Path (Join-Path $OutputDir "sample-white-product-tall.png")

$briefPath = Join-Path $OutputDir "sample-brief.txt"
$briefText = @"
Sample brief 1:
Create a Taobao main image and highlight corrosion resistance plus customization.

Sample brief 2:
Make a darker premium version, shorten the title, and keep the high-strength selling point.
"@
$briefText | Set-Content -Encoding UTF8 $briefPath

Write-Output "Created demo assets in $OutputDir"
