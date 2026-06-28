# 运行全部 Agent 单元测试
param(
    [switch]$Verbose,
    [string]$Filter = ""
)

. "$PSScriptRoot\common.ps1"

$Root = Get-ProjectRoot
Initialize-AgentEnv -Root $Root | Out-Null
Set-Location $Root

$args = @("-m", "pytest", "tests/agent")
if ($Verbose) { $args += "-v" } else { $args += "-q" }
if ($Filter) { $args += "-k", $Filter }

Write-Host "==> Running tests..." -ForegroundColor Cyan
python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Checking WS types sync..." -ForegroundColor Cyan
python (Join-Path $Root "scripts\check_ws_types_sync.py")
exit $LASTEXITCODE
