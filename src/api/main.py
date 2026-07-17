"""
FastAPI Application
Main entry point for AI Study Companion API
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.api.middleware.error_handlers import (
    database_exception_handler,
    general_exception_handler,
    validation_exception_handler,
)
from src.api.middleware.metrics import MetricsMiddleware
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.config.database import check_database_connection, engine
from src.config.settings import settings
from src.models.base import Base
from src.utils.logging_config import setup_logging


def parse_allowed_origins(value: str) -> list[str]:
    """Parse the ALLOWED_ORIGINS setting into a list for CORSMiddleware.

    "*" (or empty/whitespace-only) means "allow all" and is passed through
    as-is. Otherwise the value is split on commas with whitespace stripped.
    If "*" appears anywhere in a comma-separated list, it collapses the
    whole list to allow-all ["*"] rather than mixing "*" with exact origins.
    """
    value = value.strip()
    if not value or value == "*":
        return ["*"]
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if "*" in origins:
        return ["*"]
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger = logging.getLogger(__name__)
    logger.info("Starting AI Study Companion API...")

    # Setup logging
    setup_logging()

    # Store environment in app state for error handling
    app.state.environment = settings.environment

    # Verify database connection
    if not check_database_connection():
        logger.error("Database connection failed on startup")
        raise RuntimeError("Database connection failed on startup")
    logger.info("Database connection verified")

    # Verify JWT secret is configured
    if not settings.jwt_secret:
        logger.critical("JWT_SECRET is not configured")
        raise RuntimeError("JWT_SECRET must be configured")

    yield

    # Shutdown
    logger.info("Shutting down AI Study Companion API...")


# Create FastAPI app
app = FastAPI(
    title="AI Study Companion API",
    description="Persistent AI agent supporting students between tutoring sessions",
    version="1.1.4",
    lifespan=lifespan,
    redirect_slashes=False,  # Disable automatic trailing slash redirects to prevent HTTP redirects behind proxy
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Request logging middleware
if settings.environment == "development":
    app.add_middleware(RequestLoggingMiddleware)

# Metrics middleware (always enabled)
app.add_middleware(MetricsMiddleware)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AI Study Companion API",
        "version": "1.1.4",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = check_database_connection()
    body = {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
    }
    return JSONResponse(content=body, status_code=200 if db_status else 503)


@app.get("/metrics")
async def get_metrics():
    """
    Get application metrics

    Note: In production, protect this endpoint with authentication
    """
    from src.utils.metrics import get_metrics

    metrics = get_metrics()
    return {"success": True, "data": metrics.get_all_metrics()}


# Import routers
from src.api.handlers import (
    advanced_analytics,
    auth,
    dashboards,
    enhancements,
    goals,
    integrations,
    jobs,
    messaging,
    nudges,
    overrides,
    practice,
    progress,
    qa,
    summaries,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(summaries.router, prefix="/api/v1")
app.include_router(practice.router, prefix="/api/v1")
app.include_router(qa.router, prefix="/api/v1")
app.include_router(progress.router, prefix="/api/v1")
app.include_router(nudges.router, prefix="/api/v1")
app.include_router(overrides.router, prefix="/api/v1")
app.include_router(messaging.router, prefix="/api/v1")
app.include_router(dashboards.router, prefix="/api/v1")
app.include_router(advanced_analytics.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(enhancements.router, prefix="/api/v1")
app.include_router(goals.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
