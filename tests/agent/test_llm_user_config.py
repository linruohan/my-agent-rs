from __future__ import annotations

from pathlib import Path

import pytest
import yaml

AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"


@pytest.fixture
def config_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(AGENT_DIR / "config"))


def test_user_llm_config_merge(config_env, tmp_path):
    user_file = tmp_path / "llm_user.yaml"
    user_file.write_text(
        yaml.safe_dump(
            {
                "default_provider": "custom",
                "custom": {
                    "base_url": "https://api.example.com/v1",
                    "model": "my-model",
                },
            }
        ),
        encoding="utf-8",
    )

    from infra.config import load_llm_providers_config

    cfg = load_llm_providers_config()
    assert cfg["default_provider"] == "custom"
    assert cfg["providers"]["custom"]["base_url"] == "https://api.example.com/v1"
    assert cfg["providers"]["custom"]["model"] == "my-model"
    assert cfg["providers"]["custom"]["api_key_env"] == "CUSTOM_API_KEY"


def test_save_and_load_user_llm_config(config_env):
    from infra.config import load_user_llm_config, save_user_llm_config

    save_user_llm_config(
        {
            "default_provider": "custom",
            "custom": {"base_url": "https://x.com/v1", "model": "gpt-test"},
        }
    )
    loaded = load_user_llm_config()
    assert loaded["default_provider"] == "custom"
    assert loaded["custom"]["model"] == "gpt-test"
