from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from infra.weather_context import (
    extract_city_name,
    fetch_weather_for_query,
    is_weather_query,
    normalize_city_name,
    resolve_city_code,
    weather_page_url,
    _parse_city_code_from_search,
)


def test_is_weather_query():
    assert is_weather_query("西安今日天气")
    assert is_weather_query("What's the weather in Beijing")
    assert not is_weather_query("写一个快排算法")


def test_extract_city_name():
    assert extract_city_name("西安今日天气") == "西安"
    assert extract_city_name("查询北京的天气") == "北京"
    assert extract_city_name("西安市天气怎么样") == "西安"
    assert extract_city_name("今天天气怎么样") is None


def test_normalize_city_name():
    assert normalize_city_name("西安市") == "西安"
    assert normalize_city_name("北京") == "北京"


def test_parse_city_code_from_search():
    payload = 'success_jsonpCallback([{"ref":"101110101~西安~0~陕西~西安~陕西~CN~101110101~"}])'
    assert _parse_city_code_from_search(payload) == "101110101"


def test_resolve_city_code_from_builtin_map():
    assert resolve_city_code("西安") == "101110101"
    assert resolve_city_code("西安市") == "101110101"


def test_weather_page_url():
    assert weather_page_url("101110101") == "http://www.weather.com.cn/weather/101110101.shtml"
    assert (
        weather_page_url("101180907004")
        == "http://forecast.weather.com.cn/town/weathern/101180907004.shtml"
    )


def test_fetch_weather_for_query_uses_mocked_http(monkeypatch):
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text
            self.encoding = "utf-8"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str):
            self.calls += 1
            if "search?cityname=" in url:
                return FakeResponse(
                    '[{"ref":"101110101~西安~0~陕西~西安~陕西~CN~101110101~"}]'
                )
            if "weather/101110101.shtml" in url:
                return FakeResponse(
                    "<html><body><h1>西安</h1><p>晴 25/12℃ 微风</p></body></html>"
                )
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("infra.weather_context.httpx.Client", FakeClient)

    result = fetch_weather_for_query("西安今日天气")
    assert result is not None
    assert "中国天气网预报" in result
    assert "西安" in result
    assert "weather.com.cn/weather/101110101.shtml" in result
    assert "晴" in result
