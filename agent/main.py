from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
AGENT_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if getattr(sys, "frozen", False):
    meipass = Path(getattr(sys, "_MEIPASS", AGENT_DIR))
    os.environ.setdefault("AGENT_CONFIG_DIR", str(meipass / "config"))

import uvicorn
from fastapi import FastAPI

from agent.graph import create_agent_graph, create_sqlite_checkpointer
from agent.runner import AgentRunner
from api.config_route import router as config_router
from api.health import router as health_router
from api.health import VERSION
from api.tools_route import create_tools_router
from api.ws import create_ws_router, manager
from infra.hitl import hitl_timeout_manager
from infra.config import load_app_config, load_effective_tools_config
from infra.scheduler import get_scheduler, shutdown_scheduler
from infra.session_store import SessionStore
from tools.registry import build_registry


def _uvicorn_log_config() -> dict:
    """Send uvicorn logs to stderr so stdout stays clean for READY port= (Tauri pipe)."""
    import copy

    from uvicorn.config import LOGGING_CONFIG

    cfg = copy.deepcopy(LOGGING_CONFIG)
    for handler in ("default", "access"):
        cfg["handlers"][handler]["stream"] = "ext://sys.stderr"
    return cfg


def build_app(port: int = 8765) -> FastAPI:
    tools_cfg = load_effective_tools_config()
    registry = build_registry(tools_cfg)
    runner = AgentRunner(None, registry)
    session_store = SessionStore()

    from infra.auth import get_or_create_token

    get_or_create_token()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from loguru import logger

        checkpointer, conn = await create_sqlite_checkpointer()
        app.state.checkpointer = checkpointer
        app.state.conn = conn
        app.state.registry = registry
        runner.graph = create_agent_graph(registry, checkpointer)

        get_scheduler()

        async def _scheduler_notify(title: str, message: str) -> None:
            await manager.broadcast(
                {
                    "type": "scheduler.reminder",
                    "title": title,
                    "message": message,
                }
            )

        from infra.scheduler import set_notify_callback

        set_notify_callback(
            lambda title, message: asyncio.create_task(_scheduler_notify(title, message))
        )
        mcp_cfg = tools_cfg.get("mcp_servers", {})
        if any(v.get("enabled") for v in mcp_cfg.values()):
            tools = await registry.resolve_all(include_mcp=True)
            runner.graph = create_agent_graph(registry, checkpointer)
            logger.info("MCP enabled; {} tools available", len(tools))
        try:
            yield
        finally:
            shutdown_scheduler()
            await conn.close()

    app = FastAPI(title="Personal Assistant Agent", version=VERSION, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(create_tools_router(registry, runner))
    ws_router = create_ws_router(runner, session_store, port)
    app.include_router(ws_router)

    @app.post("/shutdown")
    async def shutdown():
        asyncio.get_event_loop().call_later(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM))
        return {"status": "shutting_down"}

    app.state.runner = runner
    app.state.session_store = session_store
    return app


def main():
    parser = argparse.ArgumentParser(description="Personal Assistant Agent Sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 = auto-assign")
    args = parser.parse_args()

    app_cfg = load_app_config()
    host = args.host or app_cfg.get("host", "127.0.0.1")
    requested_port = args.port or app_cfg.get("port", 0) or 8765

    os.environ.setdefault("AGENT_API_VERSION", app_cfg.get("version", VERSION))

    app = build_app(port=requested_port if requested_port else 8765)

    config = uvicorn.Config(
        app,
        host=host,
        port=requested_port,
        log_level="info",
        log_config=_uvicorn_log_config(),
    )
    server = uvicorn.Server(config)

    original_startup = server.startup

    async def startup_with_ready(sockets=None):
        await original_startup(sockets)
        actual_port = requested_port
        if server.servers:
            for s in server.servers:
                if s.sockets:
                    actual_port = s.sockets[0].getsockname()[1]
                    break
        print(f"READY port={actual_port}", flush=True)

    server.startup = startup_with_ready
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
