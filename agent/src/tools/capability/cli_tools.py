from __future__ import annotations

from typing import Any

from infra.config import load_yaml
from tools.capability.external_cli import run_external_cli


def load_cli_tools_config() -> dict[str, Any]:
    return load_yaml("cli_tools.yaml")


def create_cli_tools(bundle_config: dict[str, Any]) -> list[Any]:
    from langchain_core.tools import StructuredTool

    if not bundle_config.get("enabled", True):
        return []

    file_cfg = load_cli_tools_config()
    defaults = file_cfg.get("defaults", {})
    programs = file_cfg.get("programs", {})
    if not isinstance(programs, dict):
        return []

    default_timeout = int(
        bundle_config.get("default_timeout_sec", defaults.get("timeout_sec", 60))
    )
    default_max_chars = int(
        bundle_config.get("max_output_chars", defaults.get("max_output_chars", 80000))
    )
    default_risk = bundle_config.get("default_risk", defaults.get("risk", "low"))

    tools: list[Any] = []

    for prog_id, prog in programs.items():
        if not isinstance(prog, dict) or not prog.get("enabled"):
            continue

        tool_name = str(prog.get("tool_name") or prog_id).strip()
        binaries = prog.get("binaries") or [prog_id]
        if isinstance(binaries, str):
            binaries = [binaries]
        primary = str(binaries[0])
        description = str(
            prog.get("description")
            or f"Run {primary} CLI in the assistant workspace."
        )
        allowed = list(prog.get("allowed_prefixes") or [])
        confirm = list(prog.get("confirm_prefixes") or [])
        timeout = int(prog.get("timeout_sec", default_timeout))
        max_chars = int(prog.get("max_output_chars", default_max_chars))
        risk = prog.get("risk", default_risk)
        requires_confirmation = bool(prog.get("requires_confirmation", False))
        aliases = [str(b) for b in binaries[1:]]

        def _runner(
            args: str = "",
            *,
            _primary: str = primary,
            _aliases: list[str] = aliases,
            _allowed: list[str] = allowed,
            _confirm: list[str] = confirm,
            _timeout: int = timeout,
            _max_chars: int = max_chars,
        ) -> str:
            return run_external_cli(
                _primary,
                args,
                binary_aliases=_aliases,
                allowed_prefixes=_allowed or None,
                confirm_prefixes=_confirm or None,
                timeout=_timeout,
                max_output_chars=_max_chars,
            )

        tool = StructuredTool.from_function(
            func=_runner,
            name=tool_name,
            description=(
                f"{description} "
                "Pass arguments only (no shell operators); runs in workspace directory."
            ),
        )
        tool._cli_meta = {  # type: ignore[attr-defined]
            "risk": risk,
            "requires_confirmation": requires_confirmation,
            "program_id": prog_id,
        }
        tools.append(tool)

    return tools


def cli_tool_meta(tool: Any) -> dict[str, Any]:
    return getattr(tool, "_cli_meta", {})
