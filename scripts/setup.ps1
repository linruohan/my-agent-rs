# 初始化开发环境：安装 Python / Node 依赖
param(
    [switch]$SkipSidecarBuild
)

. "$PSScriptRoot\common.ps1"

$Root = Get-ProjectRoot
Set-Location $Root

Write-Host "==> Setup Personal Assistant Agent" -ForegroundColor Cyan
Assert-Dependencies

if (-not (Test-CommandExists "npm")) {
    throw "Node.js/npm not found. Install Node.js 20 LTS."
}

Write-Host "==> Installing Python dependencies..." -ForegroundColor Yellow
Set-Location (Join-Path $Root "agent")
python -m pip install --upgrade pip -q
python -m pip install -e ".[dev]" -q
Set-Location $Root

Write-Host "==> Installing Node dependencies..." -ForegroundColor Yellow
npm install

$iconDir = Join-Path $Root "src-tauri\icons\32x32.png"
if (-not (Test-Path $iconDir)) {
    Write-Host "==> Generating placeholder icons..." -ForegroundColor Yellow
    python (Join-Path $Root "scripts\gen_icons.py")
}

Initialize-AgentEnv -Root $Root | Out-Null

Write-Host "==> Ensuring Sidecar stub for Tauri dev..." -ForegroundColor Yellow
python (Join-Path $Root "scripts\ensure_sidecar_stub.py")

if (-not $SkipSidecarBuild) {
    Write-Host "==> Setup complete." -ForegroundColor Green
} else {
    Write-Host "==> Setup complete (sidecar build skipped)." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  Web dev:     .\scripts\run-web.ps1"
Write-Host "  Desktop dev: .\scripts\run-desktop.ps1"
Write-Host "  Full build:  .\scripts\build.ps1"
