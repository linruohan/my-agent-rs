#!/usr/bin/env bash
# 项目根目录构建入口：测试 + 前端 + Sidecar + Tauri 桌面包
#
# 用法:
#   ./build.sh                 完整构建
#   ./build.sh --dev-only      仅构建前端 (dist/)
#   ./build.sh --skip-tests    跳过 agent 测试
#   ./build.sh --skip-sidecar  跳过 Sidecar (PyInstaller)
#   ./build.sh --skip-tauri    跳过 Tauri 桌面包
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT/scripts/build.sh" "$@"
