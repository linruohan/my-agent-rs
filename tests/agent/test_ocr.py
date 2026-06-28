from __future__ import annotations

import base64
import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))


def test_ocr_progress_text():
    from ocr.worker import ocr_progress_text

    assert ocr_progress_text() == "正在识别中…"


def test_is_ocr_only_request():
    from ocr.compose import is_ocr_only_request

    imgs = [{"type": "image", "path": "a.png"}]
    assert is_ocr_only_request("", imgs)
    assert is_ocr_only_request("识别文本", imgs)
    assert is_ocr_only_request("/ocr", imgs)
    assert not is_ocr_only_request("请总结图片内容", imgs)
    assert not is_ocr_only_request("", [{"type": "file", "path": "a.txt"}])


def test_format_ocr_reply():
    from ocr.compose import format_ocr_reply

    assert format_ocr_reply([{"name": "a.png", "text": "你好"}]) == "你好"
    reply = format_ocr_reply(
        [{"name": "a.png", "text": "A"}, {"name": "b.png", "text": "B"}]
    )
    assert "**a.png**" in reply
    assert "A" in reply


def test_try_direct_ocr_without_images():
    from ocr.compose import try_direct_ocr_reply

    assert try_direct_ocr_reply("/ocr", None) == "请先添加图片，或使用 /ocr 时粘贴/上传图片"
    assert try_direct_ocr_reply("hello", None) is None


def test_save_temp_image_b64(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    from ocr.compose import save_temp_image_b64

    raw = base64.b64encode(b"fake-png").decode("ascii")
    saved = save_temp_image_b64(raw, ext="png")
    assert saved["ok"] is True
    assert Path(saved["path"]).is_file()


def test_ocr_engine_name_from_config(monkeypatch):
    monkeypatch.delenv("AGENT_OCR_ENGINE", raising=False)

    from infra import config as cfg_mod

    original = cfg_mod.load_tools_config

    def fake_config():
        return {"capability": {"ocr": {"engine": "rapid"}}}

    monkeypatch.setattr(cfg_mod, "load_tools_config", fake_config)
    from ocr.core import ocr_engine_name

    assert ocr_engine_name() == "rapid"
    monkeypatch.setattr(cfg_mod, "load_tools_config", original)


def test_ocr_chain_prefers_first_success(monkeypatch, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")

    from ocr import core

    calls: list[str] = []

    def rapid_ok(path):
        calls.append("rapid")
        return {"ok": True, "text": "rapid-text", "engine": "rapidocr"}

    def winrt_ok(path):
        calls.append("winrt")
        return {"ok": True, "text": "winrt-text", "engine": "winrt-ocr"}

    monkeypatch.setattr(core, "rapid_available", lambda: True)
    monkeypatch.setattr(core, "paddle_available", lambda: True)
    monkeypatch.setattr(core, "ocr_image_path_rapid", rapid_ok)
    monkeypatch.setattr(core, "ocr_image_path_paddle", lambda p: {"ok": False, "error": "skip"})
    monkeypatch.setattr(core, "_try_winrt_ocr", winrt_ok)
    monkeypatch.setenv("AGENT_OCR_ENGINE", "auto")

    result = core.ocr_image_path(img)
    assert result["ok"] is True
    assert result["text"] == "rapid-text"
    assert calls == ["rapid"]
