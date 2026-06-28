from __future__ import annotations

from typing import Any

import yaml

from infra.config import get_data_dir

USER_SETTINGS_PATH = get_data_dir() / "user_settings.yaml"


def load_user_settings() -> dict[str, Any]:
    if not USER_SETTINGS_PATH.is_file():
        return {}
    with USER_SETTINGS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
