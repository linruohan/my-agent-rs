# 快捷入口：默认启动 Web 开发模式
param(
    [ValidateSet("web", "desktop", "sidecar")]
    [string]$Mode = "web",
    [int]$Port = 8765
)

switch ($Mode) {
    "web"     { & "$PSScriptRoot\run-web.ps1" -SidecarPort $Port }
    "desktop" { & "$PSScriptRoot\run-desktop.ps1" }
    "sidecar" { & "$PSScriptRoot\run-sidecar.ps1" -Port $Port }
}
