# Sidecar Observability

## Prometheus scrape

Sidecar exposes metrics at:

- JSON: `GET http://127.0.0.1:{port}/metrics`
- Prometheus text: `GET http://127.0.0.1:{port}/metrics/prometheus`

Example `prometheus.yml` scrape config:

```yaml
scrape_configs:
  - job_name: personal-assistant-sidecar
    scrape_interval: 15s
    static_configs:
      - targets: ["127.0.0.1:8765"]
    metrics_path: /metrics/prometheus
```

## Grafana dashboard

Import `observability/grafana/personal-assistant-dashboard.json`:

1. Grafana → Dashboards → Import
2. Upload JSON or paste file contents
3. Select Prometheus datasource

### Panels

| Panel | Metric |
|-------|--------|
| Agent Turns Rate | `rate(agent_turns[5m])` |
| Latency p95 | `turn_duration_ms_p95`, `tool_call_duration_ms_p95` |
| Tool Calls Success | `tool_calls_success` |
| Tool Call Errors | `tool_calls_error` |
| RAG Ingest Requests | `rag_ingest_requests` |
| RAG Ingest Rate Limited | `rag_ingest_rate_limited` |
| RAG Ingest Throughput | `rate(rag_ingest_requests[5m])`, `rate(rag_ingest_rate_limited[5m])` |

## OpenTelemetry (optional)

```powershell
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318/v1/traces"
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

Restart Sidecar after setting environment variables.
