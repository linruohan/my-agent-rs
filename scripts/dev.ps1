# 开发模式启动脚本
param(
    [int]$SidecarPort = 8765
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting Personal Assistant Agent (dev mode)..."

# 启动 Python Sidecar
$agentDir = Join-Path $Root "agent"
$env:AGENT_CONFIG_DIR = Join-Path $agentDir "config"
$env:AGENT_DATA_DIR = Join-Path $Root "data"

Start-Process -NoNewWindow python -ArgumentList "main.py", "--port", $SidecarPort -WorkingDirectory $agentDir

Write-Host "Sidecar starting on port $SidecarPort..."
Write-Host "Run 'npm run dev' in another terminal for frontend."
