# 开发模式：Sidecar + Vite 前端（Web 浏览器访问）
param(
    [int]$SidecarPort = 8765
)

. "$PSScriptRoot\common.ps1"

$Root = Get-ProjectRoot
$paths = Initialize-AgentEnv -Root $Root

Write-Host "==> Starting Personal Assistant Agent (Web Dev)" -ForegroundColor Cyan

Clear-StaleAgentApiProcesses -Port $SidecarPort

$logFile = Join-Path $paths.DataDir "sidecar.log"
$sidecarProc = Start-Process python `
    -ArgumentList @("main.py", "--host", "127.0.0.1", "--port", "$SidecarPort") `
    -WorkingDirectory $paths.AgentDir `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $logFile `
    -PassThru `
    -WindowStyle Hidden

Write-Host "==> Sidecar PID $($sidecarProc.Id), log: $logFile"

if (-not (Wait-SidecarHealth -Port $SidecarPort)) {
    Stop-SidecarProcess -Process $sidecarProc -Port $SidecarPort
    Get-Content $logFile -Tail 20 -ErrorAction SilentlyContinue
    throw "Sidecar failed to start on port $SidecarPort"
}

Write-Host "==> Sidecar ready at http://127.0.0.1:${SidecarPort}" -ForegroundColor Green

$env:VITE_SIDECAR_PORT = "$SidecarPort"

try {
    Set-Location $Root
    Write-Host "==> Starting Vite dev server (http://localhost:1420)..." -ForegroundColor Cyan
    npm run dev
} finally {
    Write-Host "==> Stopping Sidecar..." -ForegroundColor Yellow
    Stop-SidecarProcess -Process $sidecarProc -Port $SidecarPort
}
