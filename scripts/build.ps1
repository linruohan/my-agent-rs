# 完整构建：测试 + 前端 + Sidecar + Tauri 安装包
param(
    [switch]$SkipTests,
    [switch]$SkipSidecar,
    [switch]$SkipTauri,
    [switch]$DevOnly
)

. "$PSScriptRoot\common.ps1"

$Root = Get-ProjectRoot
Initialize-AgentEnv -Root $Root | Out-Null
Set-Location $Root

Write-Host "==> Build Personal Assistant Agent" -ForegroundColor Cyan

if (-not $SkipTests) {
    Write-Host "==> Running agent tests..." -ForegroundColor Yellow
    python -m pytest tests/agent -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
}

Write-Host "==> Building frontend..." -ForegroundColor Yellow
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }

if ($DevOnly) {
    Write-Host "==> Dev build complete (dist/ ready)." -ForegroundColor Green
    exit 0
}

if (-not $SkipSidecar) {
    Write-Host "==> Building Sidecar binary (PyInstaller)..." -ForegroundColor Yellow
    python (Join-Path $Root "scripts\build_sidecar.py")
    if ($LASTEXITCODE -ne 0) { throw "Sidecar build failed" }
}

if (-not $SkipTauri) {
    if (-not (Test-CommandExists "cargo")) {
        Write-Warning "Skipping Tauri build: cargo not found."
    } else {
        Write-Host "==> Building Tauri desktop bundle..." -ForegroundColor Yellow
        if ($IsWindows -or $env:OS -match "Windows") {
            npm run tauri build -- --bundles nsis
        } else {
            npm run tauri build
        }
        if ($LASTEXITCODE -ne 0) { throw "Tauri build failed" }
    }
}

Write-Host "==> Build complete!" -ForegroundColor Green
Write-Host "  Frontend: dist/"
if (-not $SkipSidecar) { Write-Host "  Sidecar:  src-tauri/binaries/" }
if (-not $SkipTauri -and (Test-CommandExists "cargo")) {
    Write-Host "  Desktop:  src-tauri/target/release/bundle/"
}
