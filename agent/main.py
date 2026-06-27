from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import uvicorn
from fastapi import FastAPI

from agent.graph import create_agent_graph, get_checkpointer
from agent.runner import AgentRunner
from api.health import router as health_router
from api.ws import create_ws_router
from infra.config import load_app_config, load_tools_config
from infra.session_store import SessionStore
from tools.registry import build_registry

VERSION = "0.1.0"


def build_app(port: int = 8765) -> FastAPI:
    tools_cfg = load_tools_config()
    registry = build_registry(tools_cfg)
    checkpointer = get_checkpointer()
    graph = create_agent_graph(registry, checkpointer)
    runner = AgentRunner(graph, registry)
    session_store = SessionStore()

    app = FastAPI(title="Personal Assistant Agent", version=VERSION)
    app.include_router(health_router)
    app.include_router(create_ws_router(runner, session_store, port))

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

    app = build_app(port=requested_port if requested_port else 8765)

    config = uvicorn.Config(app, host=host, port=requested_port, log_level="info")
    server = uvicorn.Server(config)

    async def serve_with_ready():
        await server.serve()
        actual_port = requested_port
        if server.servers:
            for s in server.servers:
                if s.sockets:
                    actual_port = s.sockets[0].getsockname()[1]
                    break
        print(f"READY port={actual_port}", flush=True)

    # Hook into startup to print READY
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
