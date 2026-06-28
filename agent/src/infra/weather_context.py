from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

import httpx

from infra.time_context import get_current_datetime

_WEATHER_QUERY_PATTERNS = (
    r"天气",
    r"weather",
    r"气温",
    r"温度",
    r"下雨",
    r"下雪",
    r"降雨",
    r"forecast",
)

_CITY_EXTRACT_PATTERNS = (
    re.compile(r"(?:查|看|获取|查询)([\u4e00-\u9fff]{2,10}?)的?(?:今[天日])?天气"),
    re.compile(r"([\u4e00-\u9fff]{2,10}?)(?:的)?(?:今[天日]|当[前地]|本地)?天气"),
    re.compile(r"([\u4e00-\u9fff]{2,10}?)天气(?:怎么样|如何|情况)?"),
    re.compile(r"weather\s+(?:in\s+)?([a-zA-Z][a-zA-Z\s]{1,30})", re.I),
)

_LEADING_VERBS = re.compile(r"^(?:帮我|请|查询|查|看|获取|看看)\s*")

_CITY_SUFFIXES = ("市", "省", "区", "县", "自治州", "地区", "盟")

_COMMON_CITY_CODES: dict[str, str] = {
    "北京": "101010100",
    "上海": "101020100",
    "天津": "101030100",
    "重庆": "101040100",
    "广州": "101280101",
    "深圳": "101280601",
    "成都": "101270101",
    "杭州": "101210101",
    "武汉": "101200101",
    "西安": "101110101",
    "南京": "101190101",
    "苏州": "101190401",
    "郑州": "101180101",
    "长沙": "101250101",
    "青岛": "101120201",
    "大连": "101070201",
    "厦门": "101230201",
    "福州": "101230101",
    "济南": "101120101",
    "合肥": "101220101",
    "南昌": "101240101",
    "昆明": "101290101",
    "贵阳": "101260101",
    "兰州": "101160101",
    "乌鲁木齐": "101130101",
    "哈尔滨": "101050101",
    "长春": "101060101",
    "沈阳": "101070101",
    "石家庄": "101090101",
    "太原": "101100101",
    "呼和浩特": "101080101",
    "银川": "101170101",
    "西宁": "101150101",
    "拉萨": "101140101",
    "海口": "101310101",
    "三亚": "101310201",
    "南宁": "101300101",
    "香港": "101320101",
    "澳门": "101330101",
    "台北": "101340101",
}

_WEATHER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "http://www.weather.com.cn/",
}


def is_weather_query(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pattern, lower, re.I) for pattern in _WEATHER_QUERY_PATTERNS)


def normalize_city_name(city: str) -> str:
    name = city.strip()
    for suffix in _CITY_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            name = name[: -len(suffix)]
            break
    return name


def extract_city_name(text: str) -> str | None:
    cleaned = _LEADING_VERBS.sub("", text.strip())
    for pattern in _CITY_EXTRACT_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            city = normalize_city_name(match.group(1).strip())
            if city and city not in {"今天", "今日", "当地", "本地", "这里", "现在"}:
                return city
    return None


def resolve_city_code(city: str, *, client: httpx.Client | None = None) -> str | None:
    normalized = normalize_city_name(city)
    if normalized in _COMMON_CITY_CODES:
        return _COMMON_CITY_CODES[normalized]

    url = f"http://toy1.weather.com.cn/search?cityname={quote(normalized)}"
    try:
        if client is None:
            with httpx.Client(
                follow_redirects=True,
                timeout=15,
                headers=_WEATHER_HEADERS,
            ) as owned:
                resp = owned.get(url)
        else:
            resp = client.get(url)
        resp.raise_for_status()
        return _parse_city_code_from_search(resp.text)
    except Exception:
        return None


def _parse_city_code_from_search(text: str) -> str | None:
    payload = text.strip()
    if len(payload) <= 4:
        return None
    start = payload.find("[")
    end = payload.rfind("]") + 1
    if start < 0 or end <= start:
        return None
    try:
        items: list[dict[str, Any]] = json.loads(payload[start:end])
    except json.JSONDecodeError:
        return None
    if not items:
        return None
    ref = str(items[0].get("ref", ""))
    match = re.search(r"(\d{9,12})", ref)
    return match.group(1) if match else None


def weather_page_url(city_code: str) -> str:
    if len(city_code) > 9:
        return f"http://forecast.weather.com.cn/town/weathern/{city_code}.shtml"
    return f"http://www.weather.com.cn/weather/{city_code}.shtml"


def _extract_readable_html(html: str, *, max_chars: int = 12000) -> str:
    try:
        import trafilatura

        text = trafilatura.extract(html, include_links=False) or ""
        if text.strip():
            return text.strip()[:max_chars]
    except ImportError:
        pass

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_weather_page(city_code: str, *, client: httpx.Client | None = None) -> str:
    url = weather_page_url(city_code)
    if client is None:
        with httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers=_WEATHER_HEADERS,
        ) as owned:
            resp = owned.get(url)
    else:
        resp = client.get(url)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return _extract_readable_html(resp.text)


def fetch_weather_for_query(query: str) -> str | None:
    """Fetch weather from weather.com.cn when the user asks for local weather."""
    if not is_weather_query(query):
        return None

    city = extract_city_name(query)
    if not city:
        return None

    with httpx.Client(
        follow_redirects=True,
        timeout=30,
        headers=_WEATHER_HEADERS,
    ) as client:
        city_code = resolve_city_code(city, client=client)
        if not city_code:
            return None
        page_url = weather_page_url(city_code)
        try:
            content = fetch_weather_page(city_code, client=client)
        except httpx.HTTPError:
            return None

    if not content or len(content) < 8:
        return None

    now = get_current_datetime()
    return (
        f"中国天气网预报（{city}，cityId={city_code}，查询时间 {now.year}-"
        f"{now.month:02d}-{now.day:02d} {now.strftime('%H:%M')}）\n"
        f"Source: {page_url}\n\n"
        f"{content}"
    )
