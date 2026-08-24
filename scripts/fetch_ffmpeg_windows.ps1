# fetch_ffmpeg_windows.ps1
# Downloads the ffmpeg essentials build for bundling into the Windows release.
# Uses GyanD/codexffmpeg GitHub releases which provide static Windows builds
# with common codecs (h264, hls muxer, etc.) needed for screen capture.
#
# Usage:
#   .\scripts\fetch_ffmpeg_windows.ps1
#   .\scripts\fetch_ffmpeg_windows.ps1 -OutputDir "vendor/bin"

param(
    [string]$OutputDir = "vendor/bin"
)

$ErrorActionPreference = "Stop"

# Ensure output directory exists
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# Check if already downloaded
$FfmpegExe = Join-Path $OutputDir "ffmpeg.exe"
if (Test-Path $FfmpegExe) {
    $existingVersion = & $FfmpegExe -version 2>&1 | Select-Object -First 1
    Write-Host "ffmpeg already present: $existingVersion"
    Write-Host "Delete $FfmpegExe to force re-download."
    exit 0
}

# Query GitHub API for the latest release
Write-Host "Querying GitHub for latest ffmpeg release..."
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest" -UseBasicParsing
} catch {
    Write-Error "Failed to query GitHub releases API."
    exit 1
}

$Version = $release.tag_name
Write-Host "Latest version: $Version"

# Find the essentials zip asset
$asset = $release.assets | Where-Object { $_.name -like "*essentials_build.zip" } | Select-Object -First 1
if (-not $asset) {
    Write-Error "Could not find essentials_build.zip in release $Version"
    exit 1
}

$DownloadUrl = $asset.browser_download_url
$FileName = $asset.name
$TempDir = Join-Path $env:TEMP "ffmpeg-download"
$ZipPath = Join-Path $TempDir $FileName

# Download
Write-Host "Downloading ffmpeg $Version essentials build..."
Write-Host "URL: $DownloadUrl"
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
} catch {
    Write-Error "Failed to download ffmpeg from $DownloadUrl"
    exit 1
}

Write-Host "Download complete. Extracting..."

# Extract the zip
$ExtractDir = Join-Path $TempDir "extracted"
Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force

# The archive extracts to ffmpeg-<version>-essentials_build/bin/ffmpeg.exe
$InnerDir = Get-ChildItem -Path $ExtractDir -Directory | Select-Object -First 1
$BinDir = Join-Path $InnerDir.FullName "bin"

if (-not (Test-Path (Join-Path $BinDir "ffmpeg.exe"))) {
    Write-Error "ffmpeg.exe not found in extracted archive at $BinDir"
    exit 1
}

# Copy ffmpeg.exe
Copy-Item -Path (Join-Path $BinDir "ffmpeg.exe") -Destination $OutputDir -Force
Write-Host "Installed: $FfmpegExe"

# Also copy ffprobe.exe - useful for media info detection
$FfprobeSrc = Join-Path $BinDir "ffprobe.exe"
if (Test-Path $FfprobeSrc) {
    Copy-Item -Path $FfprobeSrc -Destination $OutputDir -Force
    Write-Host "Installed: $(Join-Path $OutputDir 'ffprobe.exe')"
}

# Cleanup temp files
Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue

# Verify
$installedVersion = & $FfmpegExe -version 2>&1 | Select-Object -First 1
Write-Host "Verification: $installedVersion"
Write-Host "Done. ffmpeg is ready for bundling in $OutputDir"
