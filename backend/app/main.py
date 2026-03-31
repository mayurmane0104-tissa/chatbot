import traceback
import uuid
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core import metrics


log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.starting", environment=settings.ENVIRONMENT)
    yield
    log.info("app.shutting_down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "TissaTech backend API for authentication, admin setup, widget configuration, "
        "chat streaming, and crawl-and-train pipeline.\n\n"
        "Frontend teams can use this Swagger UI for request/response formats, "
        "required headers, and endpoint behavior."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "Health, readiness, and liveness checks."},
        {"name": "auth", "description": "Admin authentication, token lifecycle, and user identity endpoints."},
        {"name": "admin", "description": "Admin dashboard APIs: analytics, crawl pipeline, documents, and widget setup."},
        {"name": "chat", "description": "Chat APIs for widget and dashboard, including SSE streaming responses."},
        {"name": "widget", "description": "Public widget bootstrap APIs using `X-Widget-Id` (or legacy `X-API-Key`)."},
        {"name": "debug", "description": "Development-only diagnostics and verification endpoints."},
        {"name": "monitoring", "description": "Prometheus metrics endpoint for monitoring stack."},
    ],
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "displayRequestDuration": True,
    },
    lifespan=lifespan,
)


# ── Global error handler — shows real errors instead of blank 500 ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    log.error("unhandled_exception", error=str(exc), path=str(request.url), traceback=tb)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# ── Security headers ──────────────────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ── Request ID ────────────────────────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{int((time.time() - start) * 1000)}ms"
    return response


# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Allow both modern widget id header and legacy API key header.
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key", "X-Widget-Id"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)

# ── Prometheus ────────────────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["monitoring"])

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import auth, chat, admin, widget, health, debug, widget_config, debug_crawl  # noqa: E402

app.include_router(health.router, tags=["health"])
app.include_router(debug.router, prefix=settings.API_PREFIX, tags=["debug"])
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
app.include_router(chat.router, prefix=f"{settings.API_PREFIX}/chat", tags=["chat"])
app.include_router(admin.router, prefix=f"{settings.API_PREFIX}/admin", tags=["admin"])
app.include_router(widget.router, prefix=f"{settings.API_PREFIX}/widget", tags=["widget"])
app.include_router(widget_config.router, prefix=f"{settings.API_PREFIX}/admin", tags=["admin"])
app.include_router(debug_crawl.router, prefix=f"{settings.API_PREFIX}/debug", tags=["debug"])
