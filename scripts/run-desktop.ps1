# 开发模式：Tauri 桌面应用（自动管理 Sidecar）
param()

. "$PSScriptRoot\common.ps1"

$Root = Get-ProjectRoot
Initialize-AgentEnv -Root $Root | Out-Null

if (-not (Test-CommandExists "cargo")) {
    Write-Warning "Rust/cargo not found. Install from https://rustup.rs for Tauri desktop build."
}

Write-Host "==> Starting Tauri desktop dev..." -ForegroundColor Cyan
Set-Location $Root

# Avoid stale local proxy breaking crate index fetch (127.0.0.1:31180/31181)
$env:NO_PROXY = "*"
$env:HTTP_PROXY = $null
$env:HTTPS_PROXY = $null
$env:ALL_PROXY = $null
$env:http_proxy = $null
$env:https_proxy = $null
$env:all_proxy = $null
# Override nightly-only flags from ~/.cargo/config.toml [env]
$env:RUSTFLAGS = ""

npm run tauri dev
