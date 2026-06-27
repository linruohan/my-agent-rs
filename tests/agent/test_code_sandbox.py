from __future__ import annotations

from tools.capability.code_sandbox import SandboxConfig, SandboxRunner, create_code_execution_tool


def test_sandbox_run_python():
    runner = SandboxRunner(SandboxConfig(timeout=10, network=False))
    result = runner.run_python("print(2 + 2)")
    assert "4" in result


def test_sandbox_blocks_disallowed_import():
    runner = SandboxRunner(SandboxConfig(timeout=10))
    result = runner.run_python("import os\nprint('fail')")
    assert "not allowed" in result.lower() or "ImportError" in result or "stderr" in result


def test_code_execution_tool():
    tool = create_code_execution_tool({"timeout_sec": 10, "network": False})
    result = tool.invoke({"code": "print('sandbox ok')", "language": "python"})
    assert "sandbox ok" in result
