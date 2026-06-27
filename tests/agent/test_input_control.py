from __future__ import annotations

import sys
import types

import pytest


def test_execute_type_mocked(monkeypatch):
    fake = types.ModuleType("pyautogui")
    calls: list[str] = []
    fake.FAILSAFE = False
    fake.PAUSE = 0
    fake.write = lambda text, interval=0.02: calls.append(text)
    monkeypatch.setitem(sys.modules, "pyautogui", fake)

    from tools.capability.input_control import execute_input_action

    result = execute_input_action("type", "hi")
    assert calls == ["hi"]
    assert "Typed" in result


def test_execute_click_mocked(monkeypatch):
    fake = types.ModuleType("pyautogui")
    fake.FAILSAFE = False
    fake.PAUSE = 0
    clicked: list[tuple[int, int]] = []
    fake.click = lambda x, y: clicked.append((x, y))
    monkeypatch.setitem(sys.modules, "pyautogui", fake)

    from tools.capability.input_control import execute_input_action

    result = execute_input_action("click 120 340")
    assert clicked == [(120, 340)]
    assert "Clicked" in result


def test_execute_click_requires_coords(monkeypatch):
    fake = types.ModuleType("pyautogui")
    fake.FAILSAFE = False
    fake.PAUSE = 0
    fake.click = lambda x, y: None
    monkeypatch.setitem(sys.modules, "pyautogui", fake)

    from tools.capability.input_control import execute_input_action

    result = execute_input_action("click")
    assert "requires coordinates" in result


def test_disallowed_action():
    from tools.capability.input_control import execute_input_action

    result = execute_input_action("type", "x", {"allowed_actions": ["click"]})
    assert "not allowed" in result
