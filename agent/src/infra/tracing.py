from __future__ import annotations

import base64
import os
from contextlib import contextmanager
from typing import Any, Iterator

from loguru import logger

_tracer = None
_enabled = False


def setup_tracing(service_name: str | None = None) -> bool:
    """Initialize OTLP tracing when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    global _tracer, _enabled

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but OpenTelemetry packages are missing. "
            "Install optional deps: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-http"
        )
        return False

    name = service_name or os.environ.get("OTEL_SERVICE_NAME", "personal-assistant-agent")
    resource = Resource.create({"service.name": name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(name)
    _enabled = True
    logger.info("OpenTelemetry tracing enabled (endpoint={})", endpoint)
    return True


def tracing_enabled() -> bool:
    return _enabled


@contextmanager
def trace_span(name: str, **attributes: Any) -> Iterator[None]:
    if not _enabled or _tracer is None:
        yield
        return

    with _tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield


def shutdown_tracing() -> None:
    global _tracer, _enabled
    if not _enabled:
        return
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception as exc:
        logger.debug("OTEL shutdown skipped: {}", exc)
    _tracer = None
    _enabled = False
