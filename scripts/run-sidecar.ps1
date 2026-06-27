# 仅启动 Python Sidecar（前台运行）
param(
    [int]$Port = 8765,
    [string]$BindHost = "127.0.0.1"
)

. "$PSScriptRoot\common.ps1"

$Root = Get-ProjectRoot
$paths = Initialize-AgentEnv -Root $Root

Write-Host "==> Starting Sidecar on ${BindHost}:${Port}..." -ForegroundColor Cyan
Write-Host "    AGENT_DATA_DIR=$($env:AGENT_DATA_DIR)"

Set-Location $paths.AgentDir
python main.py --host $BindHost --port $Port
