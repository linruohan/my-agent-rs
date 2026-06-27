# 兼容旧用法：等同于 run-web.ps1
param(
    [int]$SidecarPort = 8765
)

& "$PSScriptRoot\run-web.ps1" -SidecarPort $SidecarPort
