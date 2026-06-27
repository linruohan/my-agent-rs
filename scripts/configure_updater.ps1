# Patch tauri.conf.json updater section from environment variables.
# Usage:
#   $env:TAURI_UPDATER_PUBKEY = "..."
#   $env:TAURI_UPDATER_ENDPOINT = "https://github.com/org/repo/releases/latest/download/latest.json"
#   $env:TAURI_UPDATER_ACTIVE = "true"
#   ./scripts/configure_updater.ps1

param(
    [string]$ConfPath = (Join-Path (Split-Path $PSScriptRoot -Parent) "src-tauri\tauri.conf.json")
)

if (-not (Test-Path $ConfPath)) {
    throw "Config not found: $ConfPath"
}

$pubkey = $env:TAURI_UPDATER_PUBKEY
$endpoint = $env:TAURI_UPDATER_ENDPOINT
$activeRaw = $env:TAURI_UPDATER_ACTIVE

if (-not $pubkey -and -not $endpoint -and -not $activeRaw) {
    Write-Host "No TAURI_UPDATER_* env vars set; skipping updater configure." -ForegroundColor Yellow
    exit 0
}

$json = Get-Content $ConfPath -Raw | ConvertFrom-Json
if (-not $json.plugins) { $json | Add-Member -NotePropertyName plugins -NotePropertyValue (@{}) }
if (-not $json.plugins.updater) {
    $json.plugins | Add-Member -NotePropertyName updater -NotePropertyValue (@{})
}

if ($pubkey) {
    $json.plugins.updater.pubkey = $pubkey
    Write-Host "Set updater.pubkey"
}
if ($endpoint) {
    $json.plugins.updater.endpoints = @($endpoint)
    Write-Host "Set updater.endpoints -> $endpoint"
}
if ($activeRaw) {
    $json.plugins.updater.active = ($activeRaw -eq "1" -or $activeRaw.ToLower() -eq "true")
    Write-Host "Set updater.active -> $($json.plugins.updater.active)"
}

$json | ConvertTo-Json -Depth 20 | Set-Content $ConfPath -Encoding UTF8
Write-Host "Updated $ConfPath" -ForegroundColor Green
