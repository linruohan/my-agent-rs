from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools.capability.web_fetch import _fallback_extract, create_web_fetch_tool, fetch_url


def test_fallback_extract():
    html = "<html><body><p>Hello World</p><script>alert(1)</script></body></html>"
    text = _fallback_extract(html)
    assert "Hello World" in text
    assert "alert" not in text


def test_fetch_url_with_mock():
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><p>Article content here</p></body></html>"
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.capability.web_fetch.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
        result = fetch_url("https://example.com", max_chars=1000)
        assert "Article content" in result or "content" in result.lower()


def test_web_fetch_tool():
    tool = create_web_fetch_tool({"max_chars": 1000, "timeout_sec": 5})
    assert tool.name == "web_fetch"
