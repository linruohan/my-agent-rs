from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from infra.config import load_app_config
from infra.time_context import get_current_datetime, is_fresh_info_query

_TIMEZONE_TO_REGION: dict[str, str] = {
    "Asia/Shanghai": "cn-zh",
    "Asia/Chongqing": "cn-zh",
    "Asia/Hong_Kong": "hk-tzh",
    "Asia/Taipei": "tw-tzh",
    "Asia/Singapore": "sg-en",
    "Asia/Tokyo": "jp-jp",
    "Asia/Seoul": "kr-kr",
    "Asia/Kolkata": "in-en",
    "Europe/London": "uk-en",
    "Europe/Berlin": "de-de",
    "Europe/Paris": "fr-fr",
    "Europe/Moscow": "ru-ru",
    "America/New_York": "us-en",
    "America/Chicago": "us-en",
    "America/Denver": "us-en",
    "America/Los_Angeles": "us-en",
    "America/Toronto": "ca-en",
    "Australia/Sydney": "au-en",
    "Pacific/Auckland": "nz-en",
}

_OFFICIAL_PRIORITY_PATTERNS = (
    r"新特性",
    r"新功能",
    r"新版本",
    r"发布",
    r"发行",
    r"changelog",
    r"release notes",
    r"what'?s new",
    r"latest version",
    r"版本说明",
    r"官方",
    r"\bpep\b",
)

_PRODUCT_OFFICIAL_SITES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\bpython\b", re.I), ["python.org", "docs.python.org", "peps.python.org"]),
    (re.compile(r"\brust\b", re.I), ["rust-lang.org", "doc.rust-lang.org"]),
    (re.compile(r"\b(?:go|golang)\b", re.I), ["go.dev", "golang.org"]),
    (re.compile(r"\bnode(?:\.js)?\b", re.I), ["nodejs.org"]),
    (re.compile(r"\breact\b", re.I), ["react.dev"]),
    (re.compile(r"\bvue(?:\.js)?\b", re.I), ["vuejs.org"]),
    (re.compile(r"\bangular\b", re.I), ["angular.dev"]),
    (re.compile(r"\btypescript\b", re.I), ["typescriptlang.org"]),
    (re.compile(r"\bdjango\b", re.I), ["djangoproject.com"]),
    (re.compile(r"\bflask\b", re.I), ["flask.palletsprojects.com"]),
    (re.compile(r"\bfastapi\b", re.I), ["fastapi.tiangolo.com"]),
    (re.compile(r"\bflutter\b", re.I), ["flutter.dev", "dart.dev"]),
    (re.compile(r"\bkubernetes|k8s\b", re.I), ["kubernetes.io"]),
    (re.compile(r"\bdocker\b", re.I), ["docker.com", "docs.docker.com"]),
    (re.compile(r"\btauri\b", re.I), ["tauri.app", "v2.tauri.app"]),
    (re.compile(r"\blangchain\b", re.I), ["python.langchain.com", "langchain.com"]),
    (re.compile(r"\bjavascript\b", re.I), ["developer.mozilla.org"]),
    (re.compile(r"\bjava\b", re.I), ["docs.oracle.com", "openjdk.org"]),
    (re.compile(r"\bkotlin\b", re.I), ["kotlinlang.org"]),
    (re.compile(r"\bswift\b", re.I), ["swift.org", "developer.apple.com"]),
]


def get_search_region(config: dict | None = None) -> str:
    cfg = config or {}
    if cfg.get("region"):
        return str(cfg["region"])
    tz_name = os.environ.get("AGENT_TIMEZONE") or load_app_config().get("timezone")
    if tz_name:
        region = _TIMEZONE_TO_REGION.get(str(tz_name))
        if region:
            return region
    return "wt-wt"


def is_official_priority_query(text: str) -> bool:
    lower = text.lower()
    if is_fresh_info_query(text):
        return True
    return any(re.search(pattern, lower, re.I) for pattern in _OFFICIAL_PRIORITY_PATTERNS)


def infer_official_domains(query: str) -> list[str]:
    domains: list[str] = []
    for pattern, candidates in _PRODUCT_OFFICIAL_SITES:
        if pattern.search(query):
            for domain in candidates:
                if domain not in domains:
                    domains.append(domain)
    return domains


def enrich_search_query(query: str) -> str:
    """Add current-year context for time-sensitive searches."""
    now = get_current_datetime()
    year = str(now.year)
    if (is_fresh_info_query(query) or is_official_priority_query(query)) and year not in query:
        return f"{query} {year}"
    return query


def build_official_site_queries(query: str, domains: list[str]) -> list[str]:
    enriched = enrich_search_query(query)
    return [f"site:{domain} {enriched}" for domain in domains]


def result_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_official_url(url: str, official_domains: list[str]) -> bool:
    host = result_domain(url)
    return any(host == domain or host.endswith(f".{domain}") for domain in official_domains)


def merge_results_prefer_official(
    official: list,
    general: list,
    *,
    official_domains: list[str],
    limit: int,
) -> list:
    seen: set[str] = set()
    merged = []

    for bucket in (official, general):
        for item in bucket:
            url = getattr(item, "url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(item)

    merged.sort(
        key=lambda item: (
            0 if is_official_url(getattr(item, "url", ""), official_domains) else 1
        )
    )
    return merged[:limit]
