param(
    [string]$ZipPath,
    [string]$DownloadUrl = "",
    [string]$BaseDir = "G:\MySQL",
    [string]$ServiceName = "MySQLEcomAgent",
    [string]$DatabaseName = "ecom_art_agent",
    [string]$AppUser = "ecom_agent",
    [string]$AppPassword = "ecom_agent",
    [string]$RootPassword = "root123456"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "==> $Message"
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Download-File([string]$PrimaryUrl, [string]$Destination) {
    $fallbackUrls = @()
    if ($PrimaryUrl -like "https://dev.mysql.com/get/*") {
        $fallbackUrls += ($PrimaryUrl -replace "^https://dev\.mysql\.com/get/", "https://cdn.mysql.com/")
    }

    $urlsToTry = @($PrimaryUrl) + $fallbackUrls
    $lastError = $null

    foreach ($candidate in $urlsToTry) {
        try {
            Write-Step "Downloading MySQL archive from $candidate"
            Invoke-WebRequest -Uri $candidate -OutFile $Destination
            return
        } catch {
            $lastError = $_
        }
    }

    if ($lastError) {
        throw $lastError
    }
}

$basePath = [System.IO.Path]::GetFullPath($BaseDir)
$packageRoot = Join-Path $basePath "packages"
$dataDir = Join-Path $basePath "data"
$logsDir = Join-Path $basePath "logs"
$configDir = Join-Path $basePath "conf"
$downloadDir = Join-Path $basePath "downloads"
$defaultsFile = Join-Path $configDir "my.ini"

New-Item -ItemType Directory -Force -Path $basePath, $packageRoot, $dataDir, $logsDir, $configDir, $downloadDir | Out-Null

if (-not $ZipPath) {
    if (-not $DownloadUrl) {
        throw "Please provide either ZipPath or DownloadUrl."
    }

    $fileName = Split-Path -Path $DownloadUrl -Leaf
    $ZipPath = Join-Path $downloadDir $fileName
    if (-not (Test-Path $ZipPath)) {
        Download-File -PrimaryUrl $DownloadUrl -Destination $ZipPath
    }
}

$serverRoot = Get-ChildItem -Path $packageRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName "bin\mysqld.exe") } |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $serverRoot) {
    Write-Step "Extracting MySQL archive"
    Expand-Archive -Path $ZipPath -DestinationPath $packageRoot -Force
    $serverRoot = Get-ChildItem -Path $packageRoot -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "bin\mysqld.exe") } |
        Sort-Object Name -Descending |
        Select-Object -First 1
}

if (-not $serverRoot) {
    throw "Could not find bin\mysqld.exe inside the extracted archive. Please use the Windows ZIP Archive package."
}

$mysqld = Join-Path $serverRoot.FullName "bin\mysqld.exe"
$mysql = Join-Path $serverRoot.FullName "bin\mysql.exe"

$normalizedBaseDir = $serverRoot.FullName.Replace("\", "/")
$normalizedDataDir = $dataDir.Replace("\", "/")
$normalizedLogsDir = $logsDir.Replace("\", "/")

$myIni = @"
[mysqld]
basedir=$normalizedBaseDir
datadir=$normalizedDataDir
port=3306
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
default-time-zone=+08:00
sql_mode=STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION
max_connections=200
log-error=$normalizedLogsDir/mysql-error.log

[client]
default-character-set=utf8mb4
"@

Write-Utf8NoBom -Path $defaultsFile -Content $myIni

if (-not (Test-Path (Join-Path $dataDir "mysql"))) {
    Write-Step "Initializing MySQL data directory"
    & $mysqld --defaults-file="$defaultsFile" --initialize-insecure --console
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Step "Registering Windows service $ServiceName"
    & $mysqld --install $ServiceName --defaults-file="$defaultsFile"
    $service = Get-Service -Name $ServiceName -ErrorAction Stop
}

if ($service.Status -ne "Running") {
    Write-Step "Starting MySQL service"
    Start-Service -Name $ServiceName
    Start-Sleep -Seconds 5
}

$bootstrapSql = @"
ALTER USER 'root'@'localhost' IDENTIFIED BY '$RootPassword';
CREATE DATABASE IF NOT EXISTS $DatabaseName CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$AppUser'@'localhost' IDENTIFIED BY '$AppPassword';
ALTER USER '$AppUser'@'localhost' IDENTIFIED BY '$AppPassword';
GRANT ALL PRIVILEGES ON $DatabaseName.* TO '$AppUser'@'localhost';
FLUSH PRIVILEGES;
"@

$sqlFile = Join-Path $basePath "bootstrap.sql"
Write-Utf8NoBom -Path $sqlFile -Content $bootstrapSql

Write-Step "Creating database and application user"
& $mysql -u root -e "SELECT 1;" *> $null
if ($LASTEXITCODE -eq 0) {
    Get-Content $sqlFile | & $mysql -u root
} else {
    Get-Content $sqlFile | & $mysql -u root "-p$RootPassword"
}

Write-Step "MySQL installation completed"
Write-Host "ServiceName: $ServiceName"
Write-Host "BaseDir: $basePath"
Write-Host "MySQL Bin: $($serverRoot.FullName)\bin"
Write-Host "Database URL: mysql+pymysql://${AppUser}:${AppPassword}@127.0.0.1:3306/${DatabaseName}?charset=utf8mb4"
