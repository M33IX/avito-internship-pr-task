from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_REQUESTS_TOTAL = Counter(
    "app_http_requests_total",
    "Total HTTP requests.",
    ("method", "path", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path", "status_code"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "app_http_requests_in_progress",
    "HTTP requests currently in progress.",
    ("method", "path"),
)
DB_QUERIES_TOTAL = Counter(
    "app_db_queries_total",
    "Total SQL queries.",
    ("operation",),
)
DB_QUERY_DURATION_SECONDS = Histogram(
    "app_db_query_duration_seconds",
    "SQL query duration in seconds.",
    ("operation",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2),
)

_INSTRUMENTED_ENGINES: set[int] = set()


class PrometheusMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive)
        method = request.method
        path = request.url.path
        start = time.perf_counter()
        status_code = 500

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            status_label = str(status_code)
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status_code=status_label,
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=path,
                status_code=status_label,
            ).observe(duration)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()


def register_engine_metrics(engine: AsyncEngine) -> None:
    sync_engine = engine.sync_engine
    engine_id = id(sync_engine)
    if engine_id in _INSTRUMENTED_ENGINES:
        return

    event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(sync_engine, "after_cursor_execute", _after_cursor_execute)
    _INSTRUMENTED_ENGINES.add(engine_id)


def metrics_response() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


def _before_cursor_execute(
    conn: Any,
    _cursor: Any,
    statement: str,
    _parameters: Any,
    _context: Any,
    _executemany: bool,
) -> None:
    query_stack: list[tuple[float, str]] = conn.info.setdefault(
        "prometheus_query_start",
        [],
    )
    query_stack.append((time.perf_counter(), _sql_operation(statement)))


def _after_cursor_execute(
    conn: Any,
    _cursor: Any,
    _statement: str,
    _parameters: Any,
    _context: Any,
    _executemany: bool,
) -> None:
    query_stack: list[tuple[float, str]] = conn.info.get("prometheus_query_start", [])
    if not query_stack:
        return

    start, operation = query_stack.pop()
    duration = time.perf_counter() - start
    DB_QUERIES_TOTAL.labels(operation=operation).inc()
    DB_QUERY_DURATION_SECONDS.labels(operation=operation).observe(duration)


def _sql_operation(statement: str) -> str:
    stripped = statement.lstrip()
    if not stripped:
        return "unknown"

    return stripped.split(maxsplit=1)[0].lower()
