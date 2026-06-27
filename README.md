# 个人助理 Agent

基于 **Tauri 2 + Vue 3 + Python (LangGraph)** 的桌面个人助理，Sidecar 架构将 Agent 推理与 UI 解耦。

## 架构

```
┌─────────────────┐     WebSocket      ┌──────────────────────┐
│  Vue 3 前端      │ ◄──────────────► │  Python Sidecar       │
│  (Pinia)        │                    │  FastAPI + LangGraph  │
└────────┬────────┘                    └──────────┬───────────┘
         │                                        │
         │  Tauri IPC                             │ 工具 / RAG / LLM
         ▼                                        ▼
┌─────────────────┐                    ┌──────────────────────┐
│  Rust 壳         │ ── 管理 Sidecar ──►│  DuckDuckGo / 文件等  │
│  托盘 / Keyring  │                    └──────────────────────┘
└─────────────────┘
```

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.11+ |
| Node.js | 20 LTS |
| Rust | stable（桌面构建） |

## 快速开始

### 1. 安装依赖

**Windows (PowerShell):**
```powershell
.\scripts\setup.ps1
# 或
npm run setup
```

**Linux / macOS:**
```bash
chmod +x scripts/*.sh
./scripts/setup.sh
# 或
npm run setup:sh
```

### 2. 配置 API Key

在应用「设置」页保存 Key，或设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
```

支持的 Provider 见 `agent/config/llm_providers.yaml`。

### 3. 运行

| 模式 | 命令 | 说明 |
|------|------|------|
| Web 开发 | `npm run dev:web` | Sidecar + Vite，浏览器访问 http://localhost:1420 |
| 桌面开发 | `npm run dev:desktop` | Tauri 自动管理 Sidecar |
| 仅 Sidecar | `npm run dev:sidecar` | 调试用，默认端口 8765 |

等价脚本：

```powershell
.\scripts\run-web.ps1          # Web
.\scripts\run-desktop.ps1      # 桌面
.\scripts\run-sidecar.ps1      # Sidecar
.\scripts\run.ps1 -Mode web    # 统一入口
```

## 构建

```powershell
# 完整构建：测试 → 前端 → Sidecar(PyInstaller) → Tauri 安装包
npm run build:all

# 仅前端 dist/
npm run build:web

# 单独打包 Sidecar
npm run build:sidecar
```

构建参数（PowerShell）：

```powershell
.\scripts\build.ps1 -SkipTests      # 跳过 pytest
.\scripts\build.ps1 -SkipSidecar    # 跳过 PyInstaller
.\scripts\build.ps1 -SkipTauri      # 跳过 Tauri bundle
.\scripts\build.ps1 -DevOnly        # 仅前端 dist
```

产物路径：

- 前端：`dist/`
- Sidecar 二进制：`src-tauri/binaries/`
- 安装包：`src-tauri/target/release/bundle/`

首次 `setup` 会自动生成 Sidecar **占位二进制**（供 Tauri 开发/`cargo check`），正式发布前请运行 `npm run build:sidecar` 替换为 PyInstaller 打包版本。

## 发布

推送 `v*` 标签触发 `.github/workflows/release.yml`，在 Linux / macOS / Windows 三平台构建安装包。

### 自动更新（可选）

`src-tauri/tauri.conf.json` 中已集成 `tauri-plugin-updater`（默认 `active: false`）。启用步骤：

1. 使用 `tauri signer generate` 生成密钥对
2. 设置环境变量并运行配置脚本：
   ```powershell
   $env:TAURI_UPDATER_PUBKEY = "<public-key>"
   $env:TAURI_UPDATER_ENDPOINT = "https://github.com/YOUR_ORG/my-agent-rs/releases/latest/download/latest.json"
   $env:TAURI_UPDATER_ACTIVE = "true"
   ./scripts/configure_updater.ps1
   ```
3. CI 发布时在 GitHub Secrets 配置 `TAURI_UPDATER_PUBKEY` 与 `TAURI_SIGNING_PRIVATE_KEY`

### MCP 扩展

在 `agent/config/tools.yaml` 中启用 MCP 服务（如 GitHub）：

```yaml
mcp_servers:
  github:
    enabled: true
    ...
```

Sidecar 启动时会自动加载 MCP 工具。需安装 `pip install -e "./agent[mcp]"`，并在设置页或环境变量中配置 `GITHUB_TOKEN`。

## 测试

```powershell
npm test
# 或
python -m pytest tests/agent -v
```

当前覆盖 Agent 核心模块、工具、RAG、HITL、Provider 降级等（52+ 用例）。

## 目录结构

```
my-agent-rs/
├── agent/              # Python Sidecar
│   ├── main.py         # 入口
│   ├── config/         # tools / llm / rag 配置
│   └── src/            # graph, tools, memory, api
├── src/                # Vue 3 前端
├── src-tauri/          # Tauri Rust 壳
├── scripts/            # 构建与运行脚本
├── tests/agent/        # Python 单元测试
└── data/               # 运行时数据（checkpoint / RAG / workspace）
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `AGENT_DATA_DIR` | 数据目录 | `<项目根>/data` |
| `AGENT_CONFIG_DIR` | 配置目录 | `<项目根>/agent/config` |
| `DEEPSEEK_API_KEY` 等 | LLM API Key | 设置页 / keyring |
| `VITE_SIDECAR_PORT` | 前端连接 Sidecar 端口 | 8765 |

## 设计文档

详见 [个人助理Agent设计文档.md](./个人助理Agent设计文档.md)。
