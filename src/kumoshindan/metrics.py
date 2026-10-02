"""Prometheus metrics for KumoShindan."""

from prometheus_client import Counter, Gauge, Histogram

INVESTIGATIONS = Counter(
    "kumoshindan_investigations_total",
    "Completed Kubernetes investigations",
    ["source", "status", "category"],
)
DURATION = Histogram(
    "kumoshindan_investigation_duration_seconds",
    "Wall-clock duration of an investigation",
    buckets=(5, 10, 20, 30, 60, 120, 300),
)
TOOL_CALLS = Counter(
    "kumoshindan_tool_calls_total",
    "Kubernetes diagnostic tool calls made by the agent",
    ["tool"],
)
TOKENS = Counter(
    "kumoshindan_llm_tokens_total",
    "LLM tokens used by direction",
    ["direction"],
)
IN_PROGRESS = Gauge(
    "kumoshindan_in_progress",
    "Investigations currently running",
)
ALERTS = Counter(
    "kumoshindan_alerts_received_total",
    "Alertmanager alerts accepted or skipped",
    ["result"],
)
