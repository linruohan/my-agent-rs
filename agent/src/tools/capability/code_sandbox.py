from __future__ import annotations

import json
import subprocess
import sys
import os
import tempfile
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SandboxConfig:
    timeout: int = 90
    allowed_imports: list[str] = field(
        default_factory=lambda: ["json", "math", "re", "datetime"]
    )
    blocked_builtins: list[str] = field(
        default_factory=lambda: ["__import__", "eval", "exec", "open", "compile"]
    )
    network: bool = False
    mem_limit_mb: int = 256
    cpu_time_sec: int = 30
    workspace: Path | None = None
    audit_log: bool = True


class SandboxRunner:
    """Restricted Python subprocess sandbox."""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()

    def _write_audit(self, event: str, detail: dict[str, Any]) -> None:
        if not self.config.audit_log:
            return
        from infra.config import get_data_dir

        log_path = get_data_dir() / "sandbox_audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **detail,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def run_python(self, code: str) -> str:
        workspace = self.config.workspace or Path(tempfile.mkdtemp(prefix="sandbox_"))
        workspace.mkdir(parents=True, exist_ok=True)
        self._write_audit(
            "sandbox_start",
            {
                "workspace": str(workspace),
                "code_len": len(code),
                "network": self.config.network,
            },
        )

        wrapper = self._build_wrapper(code)
        script_path = workspace / "_run.py"
        script_path.write_text(wrapper, encoding="utf-8")

        env = {"PYTHONDONTWRITEBYTECODE": "1"}
        if not self.config.network:
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "127.0.0.1:1"

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=str(workspace),
                env={**dict(os.environ), **env},
            )
        except subprocess.TimeoutExpired:
            self._write_audit("sandbox_timeout", {"timeout_sec": self.config.timeout})
            return f"[SANDBOX_TIMEOUT] Execution exceeded {self.config.timeout}s"
        except Exception as e:
            self._write_audit("sandbox_error", {"error": str(e)})
            return f"[SANDBOX_ERROR] {e}"

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + f"[stderr]\n{result.stderr}"
        if result.returncode != 0 and not output:
            output = f"[exit code {result.returncode}]"
        self._write_audit(
            "sandbox_end",
            {
                "returncode": result.returncode,
                "output_len": len(output),
            },
        )
        return output.strip() or "(no output)"

    def _build_wrapper(self, user_code: str) -> str:
        allowed = self.config.allowed_imports
        blocked = self.config.blocked_builtins
        return textwrap.dedent(
            f"""
            import builtins
            _allowed = {allowed!r}
            _blocked = {blocked!r}

            def _restricted_import(name, *args, **kwargs):
                base = name.split('.')[0]
                if base not in _allowed:
                    raise ImportError(f"Import '{{base}}' not allowed in sandbox")
                return builtins.__import__(name, *args, **kwargs)

            _safe_builtins = {{k: v for k, v in vars(builtins).items() if k not in _blocked}}
            _safe_builtins['__import__'] = _restricted_import
            exec_globals = {{"__builtins__": _safe_builtins}}

            exec({user_code!r}, exec_globals)
            """
        )


def create_code_execution_tool(config: dict[str, Any]):
    from langchain_core.tools import tool
    from infra.config import get_data_dir

    sandbox_cfg = SandboxConfig(
        timeout=config.get("timeout_sec", 90),
        allowed_imports=config.get(
            "allowed_imports", ["json", "math", "re", "datetime"]
        ),
        network=config.get("network", False),
        mem_limit_mb=config.get("mem_limit_mb", 256),
        cpu_time_sec=config.get("cpu_time_sec", 30),
        workspace=get_data_dir() / "workspace" / "sandbox",
    )
    runner = SandboxRunner(sandbox_cfg)

    @tool
    def code_execution(code: str, language: str = "python") -> str:
        """Execute code in a restricted sandbox and return stdout/stderr."""
        if language.lower() != "python":
            return f"Unsupported language: {language}. Only python is supported."
        return runner.run_python(code)

    return code_execution
