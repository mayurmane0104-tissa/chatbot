"""
app/core/metrics.py
Custom Prometheus metrics for TissaTech AI Agent.
Add these to your main.py to track Bedrock, chat, and business metrics.
"""
from prometheus_client import Counter, Histogram, Gauge

# ── HTTP / API ─────────────────────────────────────────────────────────────
chat_messages_total = Counter(
    "tissatech_chat_messages_total",
    "Total chat messages sent",
    ["role"],  # user / assistant
)

chat_errors_total = Counter(
    "tissatech_chat_errors_total",
    "Total chat errors",
    ["error_type"],  # bedrock_error / db_error / injection_blocked
)

active_conversations = Gauge(
    "tissatech_active_conversations_total",
    "Number of active conversations in last 24h",
)

# ── Bedrock / AI ───────────────────────────────────────────────────────────
bedrock_requests_total = Counter(
    "bedrock_requests_total",
    "Total Bedrock API calls",
    ["status"],  # success / error / throttled
)

bedrock_response_latency_ms = Histogram(
    "bedrock_response_latency_ms",
    "Bedrock response latency in milliseconds",
    buckets=[500, 1000, 2000, 3000, 5000, 8000, 10000, 15000, 30000],
)

bedrock_tokens_used_total = Counter(
    "bedrock_tokens_used_total",
    "Total tokens consumed from Bedrock",
    ["direction"],  # input / output
)

bedrock_errors_total = Counter(
    "bedrock_errors_total",
    "Total Bedrock errors by type",
    ["error_code"],  # ThrottlingException / AccessDeniedException / etc.
)

bedrock_region_requests_total = Counter(
    "tissatech_bedrock_region_requests_total",
    "Bedrock requests grouped by path, region, and result status",
    ["path", "region", "status"],  # path=agent|direct, status=success|error|throttled
)

bedrock_region_failover_total = Counter(
    "tissatech_bedrock_region_failover_total",
    "Total Bedrock region failovers",
    ["path", "from_region", "to_region", "reason"],
)

bedrock_region_latency_ms = Histogram(
    "tissatech_bedrock_region_latency_ms",
    "Bedrock end-to-end latency in milliseconds by request path and final region",
    ["path", "region"],
    buckets=[500, 1000, 2000, 3000, 5000, 8000, 10000, 15000, 30000],
)

# ── Knowledge Base ─────────────────────────────────────────────────────────
kb_search_total = Counter(
    "kb_search_total",
    "Total knowledge base searches",
    ["result"],  # found / not_found
)

kb_documents_total = Gauge(
    "kb_documents_total",
    "Total indexed documents in knowledge base",
)

# ── User / Session ─────────────────────────────────────────────────────────
user_sessions_total = Counter(
    "user_sessions_total",
    "Total user sessions started",
)

user_feedback_total = Counter(
    "user_feedback_total",
    "User message feedback",
    ["type"],  # thumbs_up / thumbs_down
)

# --- Crawl / Ingestion pipeline ---
crawl_jobs_total = Counter(
    "tissatech_crawl_jobs_total",
    "Total crawl jobs by status",
    ["status"],  # success / failed / empty
)

crawl_duration_seconds = Histogram(
    "tissatech_crawl_duration_seconds",
    "Crawl duration in seconds",
    buckets=[5, 10, 20, 30, 45, 60, 90, 120, 180, 300, 600, 900],
)

crawl_pages_crawled_total = Counter(
    "tissatech_crawl_pages_crawled_total",
    "Total pages crawled across all jobs",
)

crawl_rendered_pages_total = Counter(
    "tissatech_crawl_rendered_pages_total",
    "Total pages rendered with Playwright",
)

crawl_request_errors_total = Counter(
    "tissatech_crawl_request_errors_total",
    "Total crawler request errors by type",
    ["kind"],  # timeout / request_error / unexpected
)

# --- Celery ---
celery_tasks_total = Counter(
    "tissatech_celery_tasks_total",
    "Total Celery tasks by name and status",
    ["task", "status"],  # started / success / failed
)

celery_task_duration_seconds = Histogram(
    "tissatech_celery_task_duration_seconds",
    "Celery task duration in seconds",
    ["task"],
    buckets=[1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 900],
)

# ── Usage example in bedrock_client.py ────────────────────────────────────
# from app.core.metrics import bedrock_requests_total, bedrock_response_latency_ms
#
# with bedrock_response_latency_ms.time():
#     response = await bedrock_client.invoke_agent_streaming(...)
#
# bedrock_requests_total.labels(status="success").inc()
